// A camera live, full screen, on an ESP32-S3 (firmware 0.74.0, docs/CAMERA.md "Live on the ESP32-S3 boards").
//
// The P4 decodes a stream's pictures in hardware and copies them past LVGL (live_view.cpp). An S3 has neither, so its
// camera full screen showed stills: a 16-bit BMP of the whole room, some 260 KB that its Wi-Fi brings in over a second,
// asked again 0.8 s after the last, one picture about every two seconds. Here the same stream the P4 reads comes in
// (live_feed.py, `exact`: each picture already the size of the room, so nothing is scaled on the screen), each a JPEG of
// some 25 to 40 KB, decoded in a task of its own by the TJpgDec the S3 has in its ROM into one of two RGB565 pictures in
// PSRAM; the main loop shows the newest through an LVGL image in the camera view, the other being written meanwhile.
// The app makes the next picture once the last one has left its host, so a slow decode gets fewer pictures, never older
// ones, and nothing queues up.
//
// The same API as the P4's (live_view.h): the camera view asks, opens, closes and ticks it as it does there, and goes
// back to its stills after TRIES failures. Live tiles stay stills on an S3 (tiles_stream).
//
// Straight to the panel (firmware 0.79.0, USE_SOFT_LIVE_PANEL): LVGL took about 98 ms to draw each 480 x 272 picture on
// the Guition 4848S040, which held the glass to 8 a second while a picture decoded in 21. Where the display is an RGB
// panel with one frame buffer that ESPHome's st7701s makes, and the glass is not turned, each decoded picture is copied
// into the panel's frame buffer by the stream's task, at the start of the panel's frame, past LVGL, as the P4 does: LVGL
// holds the glass while it refreshes and keeps out of the picture's spot (keep_out), so one writes there at a time and
// LVGL's own drawing never lies over the picture. Elsewhere the picture goes through an LVGL image, as before.
#include "esphome/core/defines.h"
#include "live_view.h"
#ifdef USE_SOFT_LIVE_PANEL
#include <esp_attr.h>
#include <esp_lcd_panel_rgb.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

#include "esphome/components/lvgl/lvgl_esphome.h"
// The RGB panel ESPHome's display makes, picked up as ESP-IDF makes it (-Wl,--wrap=esp_lcd_new_rgb_panel,
// smart_display/__init__.py), with a signal at the start of each of its frames; and LVGL, which says how the glass is
// turned. A build without pictures keeps only this.
namespace live_view {
static esp_lcd_panel_handle_t rgb_panel = nullptr;
static int rgb_w = 0, rgb_h = 0;
static esphome::lvgl::LvglComponent *rgb_lvgl = nullptr;
static StaticSemaphore_t vblank_store;
static SemaphoreHandle_t vblank = nullptr;
void soft_bind(esphome::lvgl::LvglComponent *lvgl) { rgb_lvgl = lvgl; }
// In the panel's interrupt, which runs while the flash is written (CONFIG_LCD_RGB_ISR_IRAM_SAFE): code in IRAM, data
// inside the chip.
static bool IRAM_ATTR on_vblank(esp_lcd_panel_handle_t, const esp_lcd_rgb_panel_event_data_t *, void *) {
  BaseType_t woken = pdFALSE;
  xSemaphoreGiveFromISR(vblank, &woken);
  return woken == pdTRUE;
}
static void rgb_made(esp_lcd_panel_handle_t made, const esp_lcd_rgb_panel_config_t *config) {
  // One frame buffer of 16-bit pixels, as LVGL's flush writes them; anything else keeps the LVGL image.
  const int bits = config->bits_per_pixel ? config->bits_per_pixel : config->data_width;
  if (config->num_fbs > 1 || bits != 16) return;
  rgb_panel = made;
  rgb_w = config->timings.h_res;
  rgb_h = config->timings.v_res;
  vblank = xSemaphoreCreateBinaryStatic(&vblank_store);
  esp_lcd_rgb_panel_event_callbacks_t callbacks{};
  callbacks.on_vsync = on_vblank;
  if (esp_lcd_rgb_panel_register_event_callbacks(made, &callbacks, nullptr) != ESP_OK) vblank = nullptr;
}
}  // namespace live_view
extern "C" esp_err_t __real_esp_lcd_new_rgb_panel(const esp_lcd_rgb_panel_config_t *config, esp_lcd_panel_handle_t *made);
extern "C" esp_err_t __wrap_esp_lcd_new_rgb_panel(const esp_lcd_rgb_panel_config_t *config, esp_lcd_panel_handle_t *made) {
  const esp_err_t err = __real_esp_lcd_new_rgb_panel(config, made);
  if (err == ESP_OK && made && config) live_view::rgb_made(*made, config);
  return err;
}
#endif
#if defined(USE_SOFT_LIVE) && defined(SCREEN_PICTURES)
#include <algorithm>
#include <atomic>
#include <cerrno>
#include <cstring>
#include <sys/socket.h>
#include <unistd.h>

#include <esp_heap_caps.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "esp32s3/rom/tjpgd.h"
// Espressif's decoder with the S3's SIMD (smart_display/__init__.py adds it, firmware 0.76.0): three to four times the
// ROM's TJpgDec. A build without it decodes with TJpgDec alone.
#if __has_include("esp_jpeg_dec.h")
#include "esp_jpeg_dec.h"
#define SOFT_LIVE_NEW_JPEG 1
#endif
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "lvgl.h"
#ifdef USE_SOFT_LIVE_PANEL
#include "lvgl_private.h"  // the display's list of areas to draw, which LVGL 9 keeps out of lvgl.h
#endif

// LVGL's own (misc/cache/instance/lv_image_cache.h), which lvgl.h leaves out of this build: what LVGL kept of an image
// descriptor whose pixels changed is let go.
extern "C" void lv_image_cache_drop(const void *src);

namespace live_view {

static const char *const TAG = "live";
// A picture's JPEG at most: a room of 480 x 430 at the app's quality is 8 to 40 KB. Its share of the pictures' budget
// (held_bytes) is this, so no more than needed (firmware 0.77.0, 256 KB before).
constexpr size_t INPUT = 96 * 1024;
constexpr size_t CHUNK = 4096;
constexpr size_t WORK = 4096;          // TJpgDec's pool (3100 bytes for its tables and a 16 x 16 MCU, with room)
constexpr uint32_t WAIT_MS = 4000;
constexpr int SOFT_STREAMS = 1;        // the full view alone

// One decoded picture: RGB565 as LVGL draws it, `w` x `h` (the JPEG's size, at most the room's).
struct Frame {
  uint16_t *px = nullptr;
  lv_image_dsc_t dsc{};
  int w = 0, h = 0;
  bool still = false;
};
struct Stream {
  std::string url;
  Rect area;
  std::atomic<bool> stopping{false}, done{false}, failed{false};
  uint8_t *input = nullptr, *work = nullptr;
  Frame frames[2];
  size_t frame_bytes = 0;
  // The hand-over between the task and the main loop, under `lock`: the task decodes into the frame that is not on the
  // glass, and says it is `ready`; the main loop puts it on the glass (`showing`). A frame decoded while the last one
  // still waited takes its place: the newest wins.
  portMUX_TYPE lock = portMUX_INITIALIZER_UNLOCKED;
  int ready = -1, showing = -1;
  std::atomic<uint32_t> decoded{0}, bytes{0}, decode_us{0}, broken{0}, passed{0};
  // Straight to the panel: where the last picture lies (`armed` once the first is there), under `spot_lock`, and the
  // pictures copied there with the time it took.
  bool direct = false;
  portMUX_TYPE spot_lock = portMUX_INITIALIZER_UNLOCKED;
  Rect spot;
  bool armed = false;
  std::atomic<uint32_t> copied{0}, copy_us{0};
  std::atomic<bool> live{false};
  // The main loop's own.
  lv_obj_t *image = nullptr;
  uint32_t shown = 0, started_at = 0, reported_at = 0, reported_decoded = 0, reported_bytes = 0, reported_decode = 0,
           reported_shown = 0, reported_passed = 0, reported_copy = 0;
  bool told_first = false, told_live = false;
};
static Stream *streams[SOFT_STREAMS] = {};
static void show(Stream &s);
// LVGL's timer that puts each picture on the glass (firmware 0.77.0): it runs in LVGL's own loop, right before LVGL
// draws, every few ms, where the camera's 50 ms interval (tick) held a picture up to 50 ms and the glass to 20 a second.
static lv_timer_t *pacer = nullptr;
static void pace(lv_timer_t *) {
  for (auto *s : streams)
    if (s) show(*s);
}
#ifdef USE_SOFT_LIVE_PANEL
// ---- Straight to the panel ----
// One writer on the glass at a time, as on a P4 (live_view.cpp): LVGL for the whole of each refresh (REFR_START to
// REFR_READY, its flush being a copy into the same frame buffer), the stream's task for each copy of a picture.
// Recursive: close() takes it too, also from inside a refresh.
static SemaphoreHandle_t glass = nullptr;
static uint16_t *glass_px = nullptr;
static void hold_glass(lv_event_t *) { xSemaphoreTakeRecursive(glass, portMAX_DELAY); }
static void release_glass(lv_event_t *) { xSemaphoreGiveRecursive(glass); }
static bool turned() { return !rgb_lvgl || rgb_lvgl->get_rotation() != esphome::display::DISPLAY_ROTATION_0_DEGREES; }
// The room LVGL keeps out of: where the stream's last picture lies, once the first is there.
static bool armed_room(lv_area_t &room) {
  for (auto *s : streams) {
    if (!s || !s->direct) continue;
    portENTER_CRITICAL(&s->spot_lock);
    const bool armed = s->armed;
    const Rect r = s->spot;
    portEXIT_CRITICAL(&s->spot_lock);
    if (!armed) continue;
    room = {r.x, r.y, r.x + r.w - 1, r.y + r.h - 1};
    return true;
  }
  return false;
}
// What LVGL is about to draw (LV_EVENT_RENDER_START: its areas joined, nothing drawn yet), less the picture's room, as
// live_view.cpp does on a P4: a card behind the view, the view's own black or spinner, would otherwise lie over the
// picture until the next one. Each piece goes through the display's own rounding, as LVGL's own areas do.
static void keep_out(lv_event_t *) {
  lv_area_t room;
  if (!armed_room(room)) return;
  lv_display_t *display = lv_display_get_default();
  lv_area_t kept[LV_INV_BUF_SIZE];
  int count = 0;
  bool full = false;
  const auto add = [&](const lv_area_t &a) {
    if (count == LV_INV_BUF_SIZE) full = true;
    else kept[count++] = a;
  };
  const auto cut = [&](const lv_area_t &r) {
    lv_area_t common;
    if (!lv_area_intersect(&common, &r, &room)) {
      add(r);
      return;
    }
    if (r.y1 < room.y1) add({r.x1, r.y1, r.x2, room.y1 - 1});
    if (r.y2 > room.y2) add({r.x1, room.y2 + 1, r.x2, r.y2});
    if (r.x1 < room.x1) add({r.x1, common.y1, room.x1 - 1, common.y2});
    if (r.x2 > room.x2) add({room.x2 + 1, common.y1, r.x2, common.y2});
  };
  for (uint32_t i = 0; i < display->inv_p && !full; ++i)
    if (!display->inv_area_joined[i]) cut(display->inv_areas[i]);
  if (full) {
    // More pieces than LVGL's list holds: the whole glass less the room (four pieces at most).
    count = 0;
    full = false;
    cut({0, 0, lv_display_get_horizontal_resolution(display) - 1, lv_display_get_vertical_resolution(display) - 1});
  }
  for (int i = 0; i < count; ++i) {
    lv_display_send_event(display, LV_EVENT_INVALIDATE_AREA, &kept[i]);
    display->inv_areas[i] = kept[i];
    display->inv_area_joined[i] = 0;
  }
  display->inv_p = count;
}
// Whether a stream opened now goes straight to the panel: the panel ESPHome made, the size LVGL draws, not turned.
static bool direct_ready() {
  if (!rgb_panel || turned()) return false;
  lv_display_t *display = lv_display_get_default();
  if (!display || lv_display_get_horizontal_resolution(display) != rgb_w ||
      lv_display_get_vertical_resolution(display) != rgb_h)
    return false;
  if (!glass_px) {
    void *buffer = nullptr;
    if (esp_lcd_rgb_panel_get_frame_buffer(rgb_panel, 1, &buffer) != ESP_OK || !buffer) return false;
    glass_px = static_cast<uint16_t *>(buffer);
  }
  if (!glass && !(glass = xSemaphoreCreateRecursiveMutex())) return false;
  static bool watching = false;
  if (!watching) {
    lv_display_add_event_cb(display, hold_glass, LV_EVENT_REFR_START, nullptr);
    lv_display_add_event_cb(display, release_glass, LV_EVENT_REFR_READY, nullptr);
    lv_display_add_event_cb(display, keep_out, LV_EVENT_RENDER_START, nullptr);
    watching = true;
  }
  return true;
}
// A decoded picture into the frame buffer, in the middle of the room. The copy starts as the panel starts a frame (it
// waits a frame's time at most for that), so the panel, reading from the top, mostly finds the picture whole.
static void put(Stream &s, const Frame &f) {
  const int x = s.area.x + (s.area.w - f.w) / 2, y = s.area.y + (s.area.h - f.h) / 2;
  if (x < 0 || y < 0 || x + f.w > rgb_w || y + f.h > rgb_h) {
    s.broken++;
    return;
  }
  if (vblank) {
    xSemaphoreTake(vblank, 0);
    xSemaphoreTake(vblank, pdMS_TO_TICKS(25));
  }
  xSemaphoreTakeRecursive(glass, portMAX_DELAY);
  if (!s.stopping) {
    const int64_t began = esp_timer_get_time();
    portENTER_CRITICAL(&s.spot_lock);
    s.spot = Rect{x, y, f.w, f.h};
    s.armed = true;
    portEXIT_CRITICAL(&s.spot_lock);
    for (int row = 0; row < f.h; ++row)
      memcpy(glass_px + static_cast<size_t>(y + row) * rgb_w + x, f.px + static_cast<size_t>(row) * f.w, f.w * 2);
    s.copy_us += static_cast<uint32_t>(esp_timer_get_time() - began);
    s.copied++;
  }
  xSemaphoreGiveRecursive(glass);
}
// Nothing of the stream writes the glass once this returns, and LVGL draws the picture's room again.
static void disarm(Stream &s) {
  xSemaphoreTakeRecursive(glass, portMAX_DELAY);
  portENTER_CRITICAL(&s.spot_lock);
  const bool was = s.armed;
  const Rect r = s.spot;
  s.armed = false;
  portEXIT_CRITICAL(&s.spot_lock);
  xSemaphoreGiveRecursive(glass);
  if (!was) return;
  const lv_area_t room{r.x, r.y, r.x + r.w - 1, r.y + r.h - 1};
  lv_inv_area(lv_display_get_default(), &room);
}
#endif
// How long LVGL takes to draw onto the glass, from its display's own events: in the log beside the decode.
static uint32_t render_began = 0, render_us = 0, renders = 0, reported_render_us = 0, reported_renders = 0;
static bool render_watched = false;
static void render_event(lv_event_t *e) {
  const uint32_t now = static_cast<uint32_t>(esp_timer_get_time());
  if (lv_event_get_code(e) == LV_EVENT_RENDER_START) {
    render_began = now;
  } else if (render_began) {
    render_us += now - render_began;
    ++renders;
    render_began = 0;
  }
}

bool available() { return soft_parent != nullptr; }

// ---- Decoding: TJpgDec reads the JPEG from memory and hands back blocks of RGB888, written here as RGB565 ----
struct Source {
  const uint8_t *data;
  size_t size, at;
  Frame *frame;
};
static UINT read_jpeg(JDEC *jd, BYTE *buffer, UINT wanted) {
  auto *s = static_cast<Source *>(jd->device);
  const size_t take = std::min<size_t>(wanted, s->size - s->at);
  if (buffer) memcpy(buffer, s->data + s->at, take);
  s->at += take;
  return static_cast<UINT>(take);
}
static UINT write_block(JDEC *jd, void *bitmap, JRECT *r) {
  auto *s = static_cast<Source *>(jd->device);
  Frame &f = *s->frame;
  const auto *rgb = static_cast<const uint8_t *>(bitmap);
  const int w = r->right - r->left + 1;
  for (int y = r->top; y <= r->bottom; ++y) {
    if (y >= f.h) { rgb += 3 * w; continue; }
    uint16_t *row = f.px + static_cast<size_t>(y) * f.w;
    for (int x = r->left; x <= r->right; ++x, rgb += 3) {
      if (x >= f.w) continue;
      row[x] = static_cast<uint16_t>(((rgb[0] & 0xF8) << 8) | ((rgb[1] & 0xFC) << 3) | (rgb[2] >> 3));
    }
  }
  return 1;
}
#ifdef SOFT_LIVE_NEW_JPEG
// Espressif's decoder, straight into the frame as RGB565 in LVGL's order. 0 when it decoded, 1 when this picture is
// one for TJpgDec (a whole-picture output of another size than w x h), -1 when it is no picture to show.
static int decode_fast(Stream &s, size_t length, Frame &f) {
  jpeg_dec_config_t config = DEFAULT_JPEG_DEC_CONFIG();
  config.output_type = JPEG_PIXEL_FORMAT_RGB565_LE;
  jpeg_dec_handle_t dec = nullptr;
  if (jpeg_dec_open(&config, &dec) != JPEG_ERR_OK || !dec) return 1;
  jpeg_dec_io_t io{};
  io.inbuf = s.input;
  io.inbuf_len = static_cast<int>(length);
  jpeg_dec_header_info_t info{};
  int result = -1, out = 0;
  if (jpeg_dec_parse_header(dec, &io, &info) == JPEG_ERR_OK && info.width <= s.area.w && info.height <= s.area.h &&
      jpeg_dec_get_outbuf_len(dec, &out) == JPEG_ERR_OK) {
    result = 1;
    if (out == static_cast<int>(info.width) * info.height * 2 && static_cast<size_t>(out) <= s.frame_bytes) {
      f.w = info.width;
      f.h = info.height;
      io.outbuf = reinterpret_cast<uint8_t *>(f.px);
      result = jpeg_dec_process(dec, &io) == JPEG_ERR_OK ? 0 : -1;
    }
  }
  jpeg_dec_close(dec);
  return result;
}
#endif
// A JPEG into frame `index`; false for one that cannot be read or larger than the room (the app sends neither).
static bool decode(Stream &s, size_t length, int index, bool still) {
  Frame &f = s.frames[index];
  f.still = still;
  const int64_t began = esp_timer_get_time();
  bool done = false;
#ifdef SOFT_LIVE_NEW_JPEG
  const int fast = decode_fast(s, length, f);
  if (fast < 0) return false;
  done = fast == 0;
#endif
  if (!done) {
    Source source{s.input, length, 0, &f};
    JDEC jd;
    if (jd_prepare(&jd, read_jpeg, s.work, WORK, &source) != JDR_OK) return false;
    if (static_cast<int>(jd.width) > s.area.w || static_cast<int>(jd.height) > s.area.h) return false;
    f.w = static_cast<int>(jd.width);
    f.h = static_cast<int>(jd.height);
    if (jd_decomp(&jd, write_block, 0) != JDR_OK) return false;
  }
  s.decode_us += static_cast<uint32_t>(esp_timer_get_time() - began);
  f.dsc.header.magic = LV_IMAGE_HEADER_MAGIC;
  f.dsc.header.cf = LV_COLOR_FORMAT_RGB565;
  f.dsc.header.w = f.w;
  f.dsc.header.h = f.h;
  f.dsc.header.stride = f.w * 2;
  f.dsc.data_size = static_cast<uint32_t>(f.w) * f.h * 2;
  f.dsc.data = reinterpret_cast<const uint8_t *>(f.px);
  return true;
}
// A picture of the stream came whole: into the frame that is not on the glass, then ready for the main loop. One that
// comes while the last decoded one still waits for the glass is read past (firmware 0.77.0): the Guition decoded 25 a
// second and showed 6, and every picture decoded for nothing took the memory bus the panel and LVGL share with it.
static void arrived(Stream &s, size_t length, bool still) {
#ifdef USE_SOFT_LIVE_PANEL
  // Straight to the panel: decoded into the one frame and copied at once; the app sends the next once this left.
  if (s.direct) {
    if (!decode(s, length, 0, still)) {
      s.broken++;
      return;
    }
    s.decoded++;
    put(s, s.frames[0]);
    if (!still) s.live = true;
    return;
  }
#endif
  int target;
  portENTER_CRITICAL(&s.lock);
  const bool waits = s.ready >= 0, skip = waits && !still;
  target = s.showing == 0 ? 1 : 0;
  // A still that comes takes the place of the one that waited; a picture read past leaves it waiting (0.77.0 took it
  // back there too, so both were lost: 15 decoded a second, 6 on the glass).
  if (!skip && s.ready == target) s.ready = -1;
  portEXIT_CRITICAL(&s.lock);
  if (skip) {
    s.passed++;
    return;
  }
  if (!decode(s, length, target, still)) {
    s.broken++;
    return;
  }
  portENTER_CRITICAL(&s.lock);
  s.ready = target;
  portEXIT_CRITICAL(&s.lock);
  s.decoded++;
  if (!still) s.live = true;
}

// ---- The task: the stream as live_view.cpp reads it ----
static void stream(Stream &s) {
  const auto address = picture_fetch::split(s.url);
  const int fd = address.ok ? picture_fetch::connect_to(address, WAIT_MS) : -1;
  if (fd < 0) {
    ESP_LOGW(TAG, "no connection to %s:%u", address.host.c_str(), address.port);
    s.failed = true;
    return;
  }
  // HTTP/1.0: the app answers without chunks, and ends the stream by closing it.
  if (!picture_fetch::send_all(fd, "GET " + address.path + " HTTP/1.0\r\nHost: " + address.host + "\r\n\r\n")) {
    ::close(fd);
    s.failed = true;
    return;
  }
  auto *chunk = static_cast<uint8_t *>(heap_caps_malloc(CHUNK, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
  if (!chunk) {
    ::close(fd);
    s.failed = true;
    return;
  }
  // Short waits, so a close is seen soon even while the app sends nothing.
  timeval step{0, 200 * 1000};
  setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &step, sizeof(step));
  Reader reader;
  uint32_t heard = esphome::millis();
  while (!s.stopping) {
    const int n = recv(fd, chunk, CHUNK, 0);
    const int error = errno;
    if (n < 0 && (error == EAGAIN || error == EWOULDBLOCK)) {
      if (esphome::millis() - heard < QUIET_MS) continue;
      ESP_LOGW(TAG, "the stream went quiet");
      s.failed = true;
      break;
    }
    if (n <= 0) {
      ESP_LOGW(TAG, "the stream ended (%d, errno %d)", n, error);
      s.failed = true;
      break;
    }
    heard = esphome::millis();
    s.bytes += n;
    // Sound has no speaker here: its parts are read past (no room), as the app sends none without `sound`.
    const bool ok = reader.feed(
        chunk, n, [&s](size_t length, bool audio) -> uint8_t * { return !audio && length <= INPUT ? s.input : nullptr; },
        [&s, &reader](size_t length, bool audio) {
          if (!audio && !s.stopping) arrived(s, length, reader.still());
        });
    if (!ok) {
      ESP_LOGW(TAG, "not a stream of pictures (answer %d)", reader.status());
      s.failed = true;
      break;
    }
  }
  ::close(fd);
  free(chunk);
}
static void task_main(void *arg) {
  auto *s = static_cast<Stream *>(arg);
  stream(*s);
  s->done.store(true, std::memory_order_release);
  vTaskDelete(nullptr);
}

static void free_stream(Stream *s) {
  if (!s) return;
  bool others = false;
  for (auto *st : streams) others = others || (st && st != s);
  if (!others && pacer) {
    lv_timer_delete(pacer);
    pacer = nullptr;
  }
  if (s->image) lv_obj_delete(s->image);
  for (auto &f : s->frames) {
    if (f.px) lv_image_cache_drop(&f.dsc);
    heap_caps_free(f.px);
  }
  heap_caps_free(s->input);
  heap_caps_free(s->work);
  delete s;
}

size_t held_bytes() {
  size_t held = 0;
  for (auto *s : streams)
    if (s) held += INPUT + (s->direct ? 1 : 2) * s->frame_bytes;
  return held;
}

Handle open(const std::string &url, const Rect &area, const Look &look, bool) {
  // The full view alone: a tile keeps its stills.
  if (look.tile || !available() || area.w <= 0 || area.h <= 0) return -1;
  int slot = -1;
  for (int i = 0; i < SOFT_STREAMS; ++i)
    if (!streams[i]) { slot = i; break; }
  if (slot < 0) return -1;
  auto *s = new (std::nothrow) Stream();
  if (!s) return -1;
  s->url = url;
  s->area = area;
  s->frame_bytes = static_cast<size_t>(area.w) * area.h * 2;
  s->input = static_cast<uint8_t *>(heap_caps_malloc(INPUT, MALLOC_CAP_SPIRAM));
  s->work = static_cast<uint8_t *>(heap_caps_malloc(WORK, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
#ifdef USE_SOFT_LIVE_PANEL
  s->direct = direct_ready();
#endif
  bool ok = s->input && s->work;
  for (int i = 0; i < (s->direct ? 1 : 2); ++i) {
    Frame &f = s->frames[i];
    f.px = static_cast<uint16_t *>(heap_caps_aligned_alloc(16, s->frame_bytes, MALLOC_CAP_SPIRAM));
    ok = ok && f.px;
  }
  if (!ok) {
    ESP_LOGW(TAG, "no memory for the live picture");
    free_stream(s);
    return -1;
  }
  s->started_at = s->reported_at = esphome::millis();
  streams[slot] = s;
  if (!pacer && !s->direct) pacer = lv_timer_create(pace, 5, nullptr);
  if (!render_watched) {
    if (auto *display = lv_display_get_default()) {
      lv_display_add_event_cb(display, render_event, LV_EVENT_RENDER_START, nullptr);
      lv_display_add_event_cb(display, render_event, LV_EVENT_RENDER_READY, nullptr);
      render_watched = true;
    }
  }
  reported_renders = renders;
  reported_render_us = render_us;
  // Core 0, below the Wi-Fi and the network's own tasks: the main loop on core 1 keeps touch and LVGL as they were.
  if (xTaskCreatePinnedToCore(task_main, "soft_live", 6144, s, 2, nullptr, 0) != pdPASS) {
    streams[slot] = nullptr;
    free_stream(s);
    return -1;
  }
  ESP_LOGI(TAG, "stream %d into %dx%d at %d,%d, decoded in software%s", slot, area.w, area.h, area.x, area.y,
           s->direct ? ", straight to the panel" : "");
  return slot;
}

void close(Handle handle) {
  if (handle < 0 || handle >= SOFT_STREAMS || !streams[handle]) return;
  streams[handle]->stopping = true;
#ifdef USE_SOFT_LIVE_PANEL
  if (streams[handle]->direct) disarm(*streams[handle]);
#endif
  // Off the glass at once: the camera view takes over its room again.
  if (streams[handle]->image) lv_obj_add_flag(streams[handle]->image, LV_OBJ_FLAG_HIDDEN);
}

// The frame that is ready onto the glass, centred in the room, in the camera view (soft_parent).
static void show(Stream &s) {
  int index;
  portENTER_CRITICAL(&s.lock);
  index = s.ready;
  s.ready = -1;
  if (index >= 0) s.showing = index;
  portEXIT_CRITICAL(&s.lock);
  if (index < 0 || s.stopping) return;
  auto *parent = static_cast<lv_obj_t *>(soft_parent ? soft_parent() : nullptr);
  if (!parent) return;
  Frame &f = s.frames[index];
  if (!s.image) {
    s.image = lv_image_create(parent);
    lv_obj_remove_flag(s.image, LV_OBJ_FLAG_CLICKABLE);
    // Its parent, the camera view, goes when the view closes: then so does this, and nothing points at it any more.
    lv_obj_add_event_cb(s.image, [](lv_event_t *e) {
      auto *gone = static_cast<lv_obj_t *>(lv_event_get_target(e));
      for (auto *st : streams)
        if (st && st->image == gone) st->image = nullptr;
    }, LV_EVENT_DELETE, nullptr);
  }
  lv_area_t at;
  lv_obj_get_coords(parent, &at);
  lv_obj_set_pos(s.image, s.area.x - at.x1 + (s.area.w - f.w) / 2, s.area.y - at.y1 + (s.area.h - f.h) / 2);
  lv_obj_set_size(s.image, f.w, f.h);
  // The same descriptor carries other pixels now: LVGL forgets what it kept of it.
  lv_image_cache_drop(&f.dsc);
  lv_image_set_src(s.image, &f.dsc);
  lv_obj_invalidate(s.image);
  s.shown++;
}

void tick(const std::function<void(Handle, Event)> &tell) {
  const uint32_t now = esphome::millis();
  for (int slot = 0; slot < SOFT_STREAMS; ++slot) {
    Stream *s = streams[slot];
    if (!s) continue;
#ifdef USE_SOFT_LIVE_PANEL
    if (s->direct) {
      // A glass turned meanwhile: the stream fails, and the view asks again for one through LVGL's image.
      if (!s->stopping && turned()) {
        s->failed = true;
        s->stopping = true;
      }
      if (s->stopping || s->done.load(std::memory_order_acquire)) disarm(*s);
      s->shown = s->copied.load();
    }
#endif
    if (s->done.load(std::memory_order_acquire)) {
      const bool ended = s->stopping && !s->failed;
      ESP_LOGI(TAG, "stream %d %s: %u pictures shown in %u s", slot, ended ? "ended" : "failed", (unsigned) s->shown,
               (unsigned) ((now - s->started_at) / 1000));
      streams[slot] = nullptr;
      free_stream(s);
      tell(slot, ended ? Event::ENDED : Event::FAILED);
      continue;
    }
    if (!pacer) show(*s);
    if (!s->told_first && s->shown > 0) {
      s->told_first = true;
      ESP_LOGI(TAG, "stream %d: first picture on the glass %u ms after it started", slot, (unsigned) (now - s->started_at));
      tell(slot, Event::FIRST);
    }
    if (s->told_first && !s->told_live && s->live.load()) {
      s->told_live = true;
      tell(slot, Event::LIVE);
    }
    // What a tester reads in the log: pictures a second, their bytes and how long each took to decode.
    if (now - s->reported_at >= REPORT_MS) {
      const uint32_t decoded = s->decoded - s->reported_decoded, bytes = s->bytes - s->reported_bytes;
      const uint32_t decode = s->decode_us - s->reported_decode, span = now - s->reported_at;
      const uint32_t shown = s->shown - s->reported_shown;
#ifdef SOFT_LIVE_NEW_JPEG
      const char *decoder = "esp_new_jpeg";
#else
      const char *decoder = "TJpgDec";
#endif
      const uint32_t passed = s->passed - s->reported_passed, drawn = renders - reported_renders;
      const uint32_t drawing = render_us - reported_render_us;
      if (s->direct) {
        const uint32_t copy = s->copy_us - s->reported_copy;
        ESP_LOGI(TAG,
                 "stream %d: %.1f pictures/s decoded, %.1f on the glass, %u KB each, decoded in %u ms (%s), copied to the "
                 "panel in %u ms, LVGL drew %.1f/s in %u ms each, %u unreadable",
                 slot, decoded * 1000.0f / span, shown * 1000.0f / span,
                 decoded ? (unsigned) (bytes / decoded / 1024) : 0u, decoded ? (unsigned) (decode / decoded / 1000) : 0u,
                 decoder, shown ? (unsigned) (copy / shown / 1000) : 0u, drawn * 1000.0f / span,
                 drawn ? (unsigned) (drawing / drawn / 1000) : 0u, (unsigned) s->broken.load());
        s->reported_copy = s->copy_us;
      } else
      ESP_LOGI(TAG,
               "stream %d: %.1f pictures/s decoded, %.1f on the glass, %.1f read past, %u KB each, decoded in %u ms (%s), "
               "LVGL drew %.1f/s in %u ms each, %u unreadable",
               slot, decoded * 1000.0f / span, shown * 1000.0f / span, passed * 1000.0f / span,
               decoded ? (unsigned) (bytes / decoded / 1024) : 0u, decoded ? (unsigned) (decode / decoded / 1000) : 0u,
               decoder, drawn * 1000.0f / span, drawn ? (unsigned) (drawing / drawn / 1000) : 0u,
               (unsigned) s->broken.load());
      s->reported_passed = s->passed;
      reported_renders = renders;
      reported_render_us = render_us;
      s->reported_shown = s->shown;
      s->reported_at = now;
      s->reported_decoded = s->decoded;
      s->reported_bytes = s->bytes;
      s->reported_decode = s->decode_us;
    }
  }
}

}  // namespace live_view
#endif
