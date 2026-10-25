// The weather cards (firmware 0.70.0): the card a tap opens (render_weather_detail), the week (render_week) and the
// forecast (render_forecast), as runtime_tiles.h declares them. Compiled on its own, as page_receiver.cpp is: every
// header of the component lands in main.cpp, and on the S3 boards it had grown to the end of the Xtensa literal
// range (docs/RELEASING.md); this takes the weather out of it.
#include "runtime_tiles.h"
namespace runtime_tiles {

void render_weather_detail(const Tile &t,bool large,int width,int height,int){
  const Extra &x=t.extra();
  if(detail_status){lv_obj_add_flag(detail_status,LV_OBJ_FLAG_HIDDEN);detail_status=nullptr;}
  const int pad=overlay_card::pad(),gap=ui::px(large?12:6),gi=ui::px(large?12:6),card_pad=ui::px(large?16:8);
  const int top=detail_bar::bottom()+gap;
  const int area_w=width-2*pad,area_h=height-top-pad,inner=area_w-2*card_pad;
  const lv_font_t *hero_font=setpoint_font?setpoint_font:(watch_value_font?watch_value_font:detail_font);
  const lv_font_t *big_icon=big_icon_font?big_icon_font:widgets[0].icon_font;
  const lv_font_t *words_font=watch_font?watch_font:detail_font,*bold=label_font?label_font:detail_font;
  const lv_font_t *line_font=control_font?control_font:detail_font,*small=small_font?small_font:detail_font;
  const auto attrs=weather_attributes(t);const int n=attrs.size();
  char now[16];if(std::isfinite(t.current))snprintf(now,sizeof(now),"%.1f°",t.current);else snprintf(now,sizeof(now),"--");
  if(!face_covers(hero_font,now))hero_font=watch_value_font?watch_value_font:detail_font;
  const std::string cond=t.available()?weather_text(t.state):tr(txt::ha_unavailable);
  std::string hl;
  if(x.forecast.size())hl=degrees(x.forecast[0].high)+" / "+degrees(x.forecast[0].low);
  const std::string feels=std::isfinite(x.feels)?fill(txt::weather_feels_like,"n",(int)std::lround(x.feels)):"";
  const int hero=std::max(line_of(hero_font),line_of(big_icon));
  int widest=0;for(auto &a:attrs)widest=std::max(widest,text_width(a.value,bold));
  // The attributes: a row of tiles (two by two where one row is too narrow), one muted line, or none.
  int per_row=n,rows=n?1:0;
  while(per_row>1&&(inner-(per_row-1)*ui::px(6))/per_row<widest+line_of(watch_icon_font?watch_icon_font:small)+ui::px(30)){per_row=(per_row+1)/2;rows=(n+per_row-1)/per_row;}
  const int tiles_h=rows*weather_chip_h()+std::max(0,rows-1)*ui::px(6);
  // The line of attributes starts with feels like, which the card's top says only where it has a third line.
  std::string line=std::isfinite(x.feels)?fill(txt::weather_feels_like,"n",(int)std::lround(x.feels)):"";
  for(auto &a:attrs){std::string next=line+(line.empty()?"":" · ")+a.value;if(text_width(next,small)<=inner)line=next;}
  const int hero_w=line_of(big_icon)+gi+text_width(now,hero_font)+gi+std::max({text_width(cond,words_font),text_width(hl,line_font),text_width(feels,line_font)})+gi;
  const int beside_w=std::max(widest+line_of(watch_icon_font?watch_icon_font:small)+ui::px(30),text_width(tr(txt::ha_weather_attribute_air_pressure),small)+ui::px(24));
  const bool beside=n&&inner-hero_w>=n*beside_w+(n-1)*ui::px(6);
  struct Option{int extra;bool title,key_in_hero,beside;};
  // The key stands at the right of the card's top bar where the name centred there leaves it room, as Home
  // Assistant's dialog puts its keys in its header; else over the forecast, or in the top card on the smallest glass.
  // Its right edge is the top bar's (detail_bar): where the outer key at the right ends on every page.
  const auto edge=detail_bar::right_slot(detail_root);
  const int key_x=edge.x+edge.w-weather_key_w(),middle=detail_bar::glass_left(detail_root)+overlay_card::screen_width()/2;
  const lv_font_t *heading=watch_font?watch_font:detail_font;
  const bool key_top=middle+text_width(t.name,heading)/2+gap<=key_x;
  if(key_top)weather_key(detail_root,key_x,edge.y+(edge.h-weather_key_h())/2,weather_view==1);
  const bool title=!key_top;
  const Option options[]={{beside?std::max(0,weather_chip_h()-hero):-1,title,false,true},{n?gi+tiles_h:-1,title,false,false},
                          {line.empty()?-1:line_of(small)+ui::px(4),title,false,false},{0,title,false,false},{0,false,!key_top,false}};
  const auto chart_proto=weather_chart_of(t,false);
  // The richest arrangement whose forecast still reaches the rain row (or the most the forecast can reach at all);
  // where none shows anything, the one that leaves the forecast the most room.
  int tiers[5],rooms[5],most=-1;
  for(int i=0;i<5;++i){
    const auto &o=options[i];tiers[i]=-2;rooms[i]=-1;
    if(o.extra<0)continue;
    const int now_h=2*card_pad+hero+o.extra;rooms[i]=area_h-now_h-gap-2*card_pad-(o.title?weather_key_h()+gi:0);
    tiers[i]=weather_view?(rooms[i]>=weather_chart::hours_need(chart_proto.fonts)?3:-1):weather_chart::week_tier(chart_proto,inner,rooms[i]);
    most=std::max(most,tiers[i]);
  }
  Option best=options[4];
  if(most<0){int room=-1;for(int i=0;i<5;++i)if(rooms[i]>room){room=rooms[i];best=options[i];}}
  else for(int i=0;i<5;++i)if(tiers[i]>=std::min(3,most)){best=options[i];break;}
  // The weather now.
  const int now_h=2*card_pad+hero+best.extra;
  auto *card=detail_card(pad,top,area_w,now_h,theme::surface(t.background));
  int right=area_w-card_pad;
  if(best.key_in_hero){right-=weather_key_w();weather_key(card,right,card_pad+(hero-weather_key_h())/2,weather_view==1);right-=gi;}
  const int words_min=std::max(text_width(cond,bold),text_width(hl,line_font));
  bool with_icon=true;const lv_font_t *tf=hero_font;
  for(int step=0;step<3;++step){
    with_icon=step==0;tf=step<2?hero_font:(watch_value_font?watch_value_font:hero_font);
    if(right-card_pad-(with_icon?line_of(big_icon)+gi:0)-text_width(now,tf)-gi>=words_min)break;
  }
  const int hero_y=best.beside?(now_h-hero)/2-card_pad:0;
  int xx=card_pad;
  if(with_icon){
    const int ih=line_of(big_icon);
    auto *art=weather_chart::create(card);lv_obj_set_pos(art,xx,card_pad+hero_y+(hero-ih)/2);lv_obj_set_size(art,ih*5/4,ih);
    // The condition's two-tone picture, the one the chart draws for a day, in the largest face.
    weather_chart::Chart c;c.icon_only=true;c.fonts=weather_fonts();c.days.push_back({"",t.available()?t.state:"exceptional"});
    // The tile's colour picture, the night's while the sun is down (firmware 0.71.0).
    c.pictures=t.weather_emoji;c.night=t.weather_night;
    weather_chart::set(art,std::move(c));
    xx+=ih+gi;
  }
  const int tw=text_width(now,tf);
  detail_text(card,now,xx,card_pad+hero_y+(hero-line_of(tf))/2,tw+2,tf,LV_TEXT_ALIGN_LEFT,theme::INK);xx+=tw+gi;
  const int rw=best.beside?std::max(0,card_pad+hero_w-xx):right-xx;
  const lv_font_t *wf=text_width(cond,words_font)<=rw?words_font:bold;
  // Feels like once: in the line of attributes where the card has it, else as the top card's third line where it fits.
  const bool in_line=!best.beside&&best.extra>0&&best.extra!=gi+tiles_h;
  const bool show_feels=!in_line&&!feels.empty()&&text_width(feels,line_font)<=rw&&line_of(wf)+2*line_of(line_font)<=hero;
  const std::string hl_line=hl;
  const bool show_hl=!hl_line.empty()&&text_width(hl_line,line_font)<=rw;
  const int lines=line_of(wf)+(show_hl?line_of(line_font):0)+(show_feels?line_of(line_font):0);
  int ty=card_pad+hero_y+(hero-lines)/2;
  detail_text(card,cond,xx,ty,std::max(1,rw),wf,LV_TEXT_ALIGN_LEFT,theme::INK);ty+=line_of(wf);
  if(show_hl){detail_text(card,hl_line,xx,ty,rw,line_font,LV_TEXT_ALIGN_LEFT,theme::MUTED);ty+=line_of(line_font);}
  if(show_feels)detail_text(card,feels,xx,ty,rw,line_font,LV_TEXT_ALIGN_LEFT,theme::MUTED);
  if(best.beside){
    const int cw=std::min(ui::px(150),(inner-hero_w-(n-1)*ui::px(6))/n),x2=card_pad+inner-(n*cw+(n-1)*ui::px(6));
    for(int i=0;i<n;++i)weather_chip(card,x2+i*(cw+ui::px(6)),(now_h-weather_chip_h())/2,cw,attrs[i]);
  }else if(best.extra==gi+tiles_h&&n){
    const int cw=(inner-(per_row-1)*ui::px(6))/per_row;
    for(int i=0;i<n;++i)weather_chip(card,card_pad+(i%per_row)*(cw+ui::px(6)),card_pad+hero+gi+(i/per_row)*(weather_chip_h()+ui::px(6)),cw,attrs[i]);
  }else if(best.extra>0)detail_text(card,line,card_pad,card_pad+hero+ui::px(4),inner,small,LV_TEXT_ALIGN_LEFT,theme::MUTED);
  // The forecast.
  const int fy=top+now_h+gap,fh=area_h-now_h-gap;
  auto *days=detail_card(pad,fy,area_w,fh,theme::surface(t.background));
  int cy=card_pad;
  if(best.title){weather_key(days,card_pad,card_pad,weather_view==1);cy+=weather_key_h()+gi;}
  if(!x.forecast.size()&&!weather_view){detail_text(days,tr(txt::weather_no_forecast),card_pad,cy,inner,small,LV_TEXT_ALIGN_LEFT,theme::MUTED);}
  else weather_chart_object(days,card_pad,cy,inner,fh-cy-card_pad,weather_chart_of(t,weather_view==1));
  card_shaped(t,picture_card_shape);
}

bool render_week(Widgets &w,const Tile &t,bool large,int width,int height){
  const Extra &x=t.extra();
  const lv_font_t *bold=w.title_font?w.title_font:lv_obj_get_style_text_font(w.title,LV_PART_MAIN),*text=w.value_font;
  const lv_font_t *temp_font=watch_value_font?watch_value_font:bold,*hero_font=setpoint_font?setpoint_font:temp_font;
  const lv_font_t *line_font=control_font?control_font:text;
  const int circle=w.base_circle>0?w.base_circle:ui::px(large?54:36),gap=ui::px(large?10:6);
  const uint32_t ink=theme::hex(theme::INK),muted=theme::hex(theme::MUTED);
  const uint32_t sky=t.available()?weather_color_raw(t.state):theme::STATE_OFF;
  char now[16];if(std::isfinite(t.current))snprintf(now,sizeof(now),"%.0f°",t.current);else snprintf(now,sizeof(now),"--");
  const std::string cond=t.available()?weather_text(t.state):tr(txt::ha_unavailable);
  const std::string feels=std::isfinite(x.feels)?fill(txt::weather_feels_like,"n",(int)std::lround(x.feels)):"";
  auto chart=weather_chart_of(t,false);
  const bool wide=width>=height*12/5;
  // Where the week goes, and whether it fits there at all.
  int cx=0,cy=0,cw=width,ch=height,col=0;
  std::string hl;if(x.forecast.size())hl=degrees(x.forecast[0].high)+" / "+degrees(x.forecast[0].low);
  const lv_font_t *tf=hero_font;
  // A card of one row: the circle with the temperature and the condition beside it, as the forecast has always had it.
  const bool low=wide&&height<circle+gap+line_of(temp_font)+line_of(line_font);
  if(low){
    // The largest face that leaves the condition its line under it, as the forecast has always had it; else the largest
    // that fits alone.
    tf=nullptr;
    for(const lv_font_t *f:{hero_font,temp_font,watch_font})if(f&&face_covers(f,now)&&line_of(f)+line_of(text)<=height){tf=f;break;}
    if(!tf)for(const lv_font_t *f:{hero_font,temp_font,watch_font})if(f&&face_covers(f,now)&&line_of(f)<=height){tf=f;break;}
    if(!tf)tf=bold;
    const bool line=line_of(tf)+line_of(text)<=height;
    col=std::min(circle,height)+gap+std::max(text_width(now,tf),line?text_width(cond,text):0)+gap;
    cx=col+gap+1+gap;cw=width-cx;
  }else if(wide){
    if(!face_covers(tf,now)||circle+gap+line_of(tf)+line_of(line_font)>height)tf=temp_font;
    col=std::max({circle+gap+std::max(text_width(t.name,bold),text_width(cond,text)),text_width(now,tf),text_width(hl,line_font)})+gap;
    cx=col+gap+1+gap;cw=width-cx;
  }else{cy=circle+gap;ch=height-cy;}
  const int tier=weather_chart::week_tier(chart,cw,ch);
  // A card of two rows or more shows the line at least; one of a single row the days.
  if(tier<0||(!low&&tier<1))return false;
  begin_extra(w,"week",width,height);
  for(auto *p:w.parts)if(p)lv_obj_add_flag(p,LV_OBJ_FLAG_HIDDEN);
  auto show=[](lv_obj_t *p){lv_obj_remove_flag(p,LV_OBJ_FLAG_HIDDEN);return p;};
  auto words=[&](unsigned i,const lv_font_t *font,int px,int py,int pw,lv_text_align_t align,const std::string &s,uint32_t color){
    auto *p=show(part_label(w,i,font,px,py,pw,align,s));
    if(lv_label_get_long_mode(p)!=LV_LABEL_LONG_DOT)lv_label_set_long_mode(p,LV_LABEL_LONG_DOT);
    set_color(p,LV_STYLE_TEXT_COLOR,lv_color_hex(color));return p;
  };
  // The head: the circle in the condition's colour with its icon, as on every other card.
  const int disc_y=low?(height-std::min(circle,height))/2:0;
  auto *disc=show(part_dot(w,0,0,disc_y,std::min(circle,height)));
  set_color(disc,LV_STYLE_BG_COLOR,lv_color_hex(t.available()?theme::tint(sky,38):theme::hex(theme::TRACK)));
  const int gh=line_of(w.icon_font);
  auto *sky_icon=words(1,w.icon_font,0,disc_y+(std::min(circle,height)-gh)/2,std::min(circle,height),LV_TEXT_ALIGN_CENTER,t.available()?weather_icon(t.state):"\U000F0595",t.available()?theme::icon(sky):theme::hex(theme::OFF));
#ifdef SD_MOD_WEATHER_EMOJI
  weather_emoji::dress(sky_icon,t.available()?t.state:"",t.weather_emoji,true,t.weather_night);
#else
  (void)sky_icon;
#endif
  const int th=line_of(bold),nh=line_of(text),hy=(circle-th-nh)/2;
  if(low){
    const int c0=std::min(circle,height)+gap,tfh=line_of(tf);
    const bool line=tfh+nh<=height;
    const int ty=(height-tfh-(line?nh:0))/2;
    words(4,tf,c0,ty,col-c0,LV_TEXT_ALIGN_LEFT,now,ink);
    if(line)words(3,text,c0,ty+tfh,col-c0,LV_TEXT_ALIGN_LEFT,cond,muted);
    auto *rule=show(part_dot(w,6,col+gap,ui::px(4),1));
    lv_obj_set_size(rule,1,height-ui::px(8));lv_obj_set_style_radius(rule,0,0);
    set_color(rule,LV_STYLE_BG_COLOR,theme::color(theme::dark?theme::RAISED_LINE:theme::LINE));
  }else if(wide){
    words(2,bold,circle+gap,hy,col-circle-gap,LV_TEXT_ALIGN_LEFT,t.name,ink);
    words(3,text,circle+gap,hy+th,col-circle-gap,LV_TEXT_ALIGN_LEFT,cond,muted);
    const int ty=circle+(height-circle-line_of(tf)-line_of(line_font))/2;
    words(4,tf,0,ty,col,LV_TEXT_ALIGN_LEFT,now,ink);
    if(!hl.empty())words(7,line_font,0,ty+line_of(tf),col,LV_TEXT_ALIGN_LEFT,hl,muted);
    auto *rule=show(part_dot(w,6,col+gap,ui::px(4),1));
    lv_obj_set_size(rule,1,height-ui::px(8));lv_obj_set_style_radius(rule,0,0);
    set_color(rule,LV_STYLE_BG_COLOR,theme::color(theme::dark?theme::RAISED_LINE:theme::LINE));
  }else{
    // The temperature large at the end of the row where it fits beside the name; the line under the name says the
    // condition, and feels like where there is room for it.
    int right=width;
    const int nw=text_width(now,temp_font);
    if(line_of(temp_font)<=circle+ui::px(6)&&width-nw-circle-gap>=ui::px(large?110:70)){
      words(4,temp_font,width-nw-2,(circle-line_of(temp_font))/2,nw+2,LV_TEXT_ALIGN_RIGHT,now,ink);right=width-nw-gap;
    }
    const int room=right-circle-gap;
    std::string line=cond;
    if(!feels.empty()&&text_width(cond+" · "+feels,text)<=room)line=cond+" · "+feels;
    words(2,bold,circle+gap,hy,room,LV_TEXT_ALIGN_LEFT,t.name,ink);
    words(3,text,circle+gap,hy+th,room,LV_TEXT_ALIGN_LEFT,line,muted);
  }
  // The week: one object that owns what it draws (weather_chart.h).
  auto *&p=w.parts[5];
  if(!p)p=weather_chart::create(w.extra);
  show(p);lv_obj_set_pos(p,cx,cy);lv_obj_set_size(p,cw,ch);
  weather_chart::set(p,std::move(chart));
  return true;
}

void render_forecast(Widgets &w,const Tile &t,bool large,int width,int height) {
  namespace ft=forecast_tile;
  // The week (render_week) on every card it fits; the forms below where it fits nowhere.
  if(render_week(w,t,large,width,height))return;
  const auto &x=t.extra();const auto &days=x.forecast;
  const lv_font_t *bold=w.title_font?w.title_font:lv_obj_get_style_text_font(w.title,LV_PART_MAIN),*text=w.value_font;
  const lv_font_t *mini=mini_icon_font?mini_icon_font:w.icon_font;
  const lv_font_t *faces[ft::FACES]={setpoint_font,watch_value_font,watch_font};
  char now_text[16];
  if(std::isfinite(t.current))snprintf(now_text,sizeof(now_text),"%.0f°",t.current);else snprintf(now_text,sizeof(now_text),"--");
  ft::Metrics m;m.large=large;
  for(int f=0;f<ft::FACES;++f){
    const bool usable=faces[f]&&face_covers(faces[f],now_text);
    m.face_h[f]=usable?lv_font_get_line_height(faces[f]):0;m.face_w[f]=usable?text_width(now_text,faces[f])+2:0;
  }
  m.text_h=lv_font_get_line_height(text);m.bold_h=lv_font_get_line_height(bold);m.icon_h=lv_font_get_line_height(mini);
  m.circle=w.base_circle>0?w.base_circle:ui::px(large?54:36);
  const std::string cond=t.available()?weather_text(t.state):tr(txt::ha_unavailable);
  std::string line=cond;
  if(std::isfinite(x.feels))line+=" · "+fill(txt::weather_feels_like,"n",(int)std::lround(x.feels));
  m.cond_w=text_width(cond,text)+2;m.line_w=text_width(line,text)+2;
  const int n=(int)std::min<size_t>(days.size(),ft::DAYS),space=ui::px(large?4:2);
  float lowest=INFINITY,highest=-INFINITY;
  for(int k=0;k<n;++k){
    const auto &f=days[k];
    const int hw=text_width(degrees(f.high),bold),lw=text_width(degrees(f.low),text);
    m.temps_w=std::max(m.temps_w,hw+space+lw);m.high_w=std::max(m.high_w,hw+2);m.low_w=std::max(m.low_w,lw+2);
    m.name_w=std::max(m.name_w,text_width(f.day,text)+2);m.row_name_w=std::max(m.row_name_w,text_width(f.day,bold)+2);
    if(std::isfinite(f.rain)&&f.rain>=30){m.rain=true;m.rain_w=std::max(m.rain_w,text_width(screen_text::percent((int)std::lround(f.rain)),text)+2);}
    if(std::isfinite(f.low))lowest=std::min(lowest,f.low);
    if(std::isfinite(f.high))highest=std::max(highest,f.high);
  }
  const bool tall=t.row_span()>1||w.full;
  const auto l=ft::layout(m,width,height,n,forecast_today(t),tall);
  const bool rows=l.form==ft::Form::rows;
  begin_extra(w,rows?"forecast_rows":"forecast",width,height);
  for(auto *p:w.parts)if(p)lv_obj_add_flag(p,LV_OBJ_FLAG_HIDDEN);
  auto show=[](lv_obj_t *p){lv_obj_remove_flag(p,LV_OBJ_FLAG_HIDDEN);return p;};
  auto paint=[](lv_obj_t *p,uint32_t color){set_color(p,LV_STYLE_TEXT_COLOR,lv_color_hex(color));};
  auto words=[&](unsigned i,const lv_font_t *font,ft::Rect r,lv_text_align_t align,const std::string &s,uint32_t color){
    auto *p=show(part_label(w,i,font,r.x,r.y,r.w,align,s));
    if(lv_label_get_long_mode(p)!=LV_LABEL_LONG_DOT)lv_label_set_long_mode(p,LV_LABEL_LONG_DOT);
    paint(p,color);return p;
  };
  const uint32_t ink=theme::hex(theme::INK),muted=theme::hex(theme::MUTED),rain=theme::foreground(theme::ha::RAIN);
  // The weather now. The circle is the look's, in the condition's colour, the icon in it as on every other card.
  const uint32_t sky=t.available()?weather_color_raw(t.state):theme::STATE_OFF;
  if(!l.circle.empty()){
    auto *disc=show(part_dot(w,0,l.circle.x,l.circle.y,l.circle.w));
    set_color(disc,LV_STYLE_BG_COLOR,lv_color_hex(t.available()?theme::tint(sky,38):theme::hex(theme::TRACK)));
    const lv_font_t *glyph=l.circle.w>=m.circle||!mini_icon_font?w.icon_font:mini_icon_font;
    const int gh=lv_font_get_line_height(glyph);
    auto *sky_icon=show(part_label(w,1,glyph,l.circle.x,l.circle.y+(l.circle.h-gh)/2,l.circle.w,LV_TEXT_ALIGN_CENTER,t.available()?weather_icon(t.state):"\U000F0595"));
    paint(sky_icon,t.available()?theme::icon(sky):theme::hex(theme::OFF));
#ifdef SD_MOD_WEATHER_EMOJI
    weather_emoji::dress(sky_icon,t.available()?t.state:"",t.weather_emoji,glyph==w.icon_font,t.weather_night);
#endif
  }
  if(l.face>=0){
    words(2,faces[l.face],l.temp,LV_TEXT_ALIGN_LEFT,now_text,ink);
    if(!l.line.empty())words(3,text,l.line,LV_TEXT_ALIGN_LEFT,l.long_line?line:cond,muted);
  }
  // The high in the title font and the low beside it in the value font, on one baseline.
  const int low_drop=(bold->line_height-bold->base_line)-(text->line_height-text->base_line);
  if(rows){
    const float span=highest>lowest?highest-lowest:1.0f;
    const bool fahrenheit=t.unit.find('F')!=std::string::npos;
    auto celsius=[&](float v){return fahrenheit?(v-32)*5/9:v;};
    for(int k=0;k<l.days;++k){
      const auto &f=days[k];const auto &r=l.rows[k];const unsigned base=4+k*6;
      words(base,bold,r.name,LV_TEXT_ALIGN_LEFT,f.day,ink);
      auto *day_icon=words(base+1,mini,r.icon,LV_TEXT_ALIGN_CENTER,weather_icon(f.condition),weather_accent(f.condition));
#ifdef SD_MOD_WEATHER_EMOJI
      weather_emoji::dress(day_icon,f.condition,t.weather_emoji);
#else
      (void)day_icon;
#endif
      if(!r.rain.empty()&&std::isfinite(f.rain)&&f.rain>=30)words(base+2,text,r.rain,LV_TEXT_ALIGN_LEFT,screen_text::percent((int)std::lround(f.rain)),rain);
      words(base+3,text,{r.low.x,r.low.y,r.low.w,r.low.h},LV_TEXT_ALIGN_RIGHT,degrees(f.low),muted);
      auto *track=show(part_bar(w,base+4,r.bar.x,r.bar.y,r.bar.w,r.bar.h));
      set_color(track,LV_STYLE_BG_COLOR,theme::color(theme::TRACK));
      auto *fill_bar=lv_obj_get_child(track,0);
      if(std::isfinite(f.low)&&std::isfinite(f.high)&&std::isfinite(lowest)){
        const int from=(int)std::lround((f.low-lowest)/span*r.bar.w),to=(int)std::lround((f.high-lowest)/span*r.bar.w);
        lv_obj_remove_flag(fill_bar,LV_OBJ_FLAG_HIDDEN);
        lv_obj_set_pos(fill_bar,std::min(from,r.bar.w-r.bar.h),0);lv_obj_set_size(fill_bar,std::max(r.bar.h,to-from),r.bar.h);
        set_color(fill_bar,LV_STYLE_BG_COLOR,lv_color_hex(theme::temperature(celsius(f.low))));
        set_color(fill_bar,LV_STYLE_BG_GRAD_COLOR,lv_color_hex(theme::temperature(celsius(f.high))));
      }else lv_obj_add_flag(fill_bar,LV_OBJ_FLAG_HIDDEN);
      words(base+5,bold,r.high,LV_TEXT_ALIGN_RIGHT,degrees(f.high),ink);
    }
    return;
  }
  // Today's pill, below everything else it stands behind.
  if(!l.pill.empty()){
    auto *pill=show(part_dot(w,4,l.pill.x,l.pill.y,0));
    lv_obj_set_size(pill,l.pill.w,l.pill.h);lv_obj_set_style_radius(pill,std::min(ui::px(large?14:9),l.pill.h/2),0);
    set_color(pill,LV_STYLE_BG_COLOR,theme::color(theme::TRACK));
    if(lv_obj_get_index(pill)!=0)lv_obj_move_to_index(pill,0);
  }
  for(int k=0;k<l.days;++k){
    const auto &f=days[k];const auto &c=l.columns[k];const unsigned base=5+k*5;
    const bool beside=!c.name.empty()&&c.name.y>c.icon.y;
    if(!c.name.empty())words(base,text,c.name,beside?LV_TEXT_ALIGN_LEFT:LV_TEXT_ALIGN_CENTER,f.day,muted);
    auto *day_icon=words(base+1,mini,c.icon,LV_TEXT_ALIGN_CENTER,weather_icon(f.condition),weather_accent(f.condition));
#ifdef SD_MOD_WEATHER_EMOJI
    weather_emoji::dress(day_icon,f.condition,t.weather_emoji);
#else
    (void)day_icon;
#endif
    const std::string hi=degrees(f.high),lo=degrees(f.low);
    const int hw=text_width(hi,bold),lw=text_width(lo,text),x0=c.temps.x+(c.temps.w-(hw+space+lw))/2;
    words(base+2,bold,{x0,c.temps.y,hw+2,c.temps.h},LV_TEXT_ALIGN_LEFT,hi,ink);
    words(base+3,text,{x0+hw+space,c.temps.y+low_drop,lw+2,m.text_h},LV_TEXT_ALIGN_LEFT,lo,muted);
    if(!c.rain.empty()&&std::isfinite(f.rain)&&f.rain>=30)words(base+4,text,c.rain,LV_TEXT_ALIGN_CENTER,screen_text::percent((int)std::lround(f.rain)),rain);
  }
}

}  // namespace runtime_tiles
