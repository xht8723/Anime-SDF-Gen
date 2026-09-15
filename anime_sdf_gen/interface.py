"""Quiet, rounded popup controls; view layout remains owned by Editor."""
import bpy
import gpu
import blf
from pathlib import Path
from .editor import scale,Rect
from .tooltips import describe
from .core import model
from .core.model import MAP_LABELS, OUTPUT_ROUTES
from .core.files import output_layout

BG=(.063,.072,.087,1)
PANEL=(.082,.092,.108,1)
BUTTON=(.119,.133,.154,1)
HOVER=(.167,.189,.216,1)
BORDER=(.195,.219,.248,1)
SELECT=(.139,.263,.286,1)
SELECT_HOVER=(.19,.35,.375,1)
ACCENT=(.48,.79,.78,1)
PRIMARY=(.34,.66,.66,1)
PRIMARY_HOVER=(.44,.77,.76,1)
TEXT=(.91,.935,.95,1)
MUTED=(.57,.63,.69,1)
WARN=(.94,.70,.50,1)


def measure(value,size):
    blf.size(0,size*scale());return blf.dimensions(0,value)[0]


def shorten(value,width,size):
    if measure(value,size)<=width:return value
    while value and measure(value+'…',size)>width:value=value[:-1]
    return value+'…' if value else ''


def wrap(value,width,size=12.5):
    result=[]
    for paragraph in value.splitlines() or ['']:
        line=''
        for word in paragraph.split():
            if line and measure(line+' '+word,size)>width:result.append(line);line=''
            while measure(word,size)>width and len(word)>1:
                cut=len(word)-1
                while cut>1 and measure(word[:cut],size)>width:cut-=1
                if line:result.append(line);line=''
                result.append(word[:cut]);word=word[cut:]
            line=(line+' '+word).strip()
        if line:result.append(line)
    return result


def icon(p,name,box,color,u):
    x,y,w,h=box;cx,cy=x+w/2,y+h/2
    paths=[]
    if name in ('UNDO','REDO'):
        sign=-1 if name=='REDO' else 1
        paths=[[(sign*a,b) for a,b in [(-7,4),(0,4),(5,1),(5,-5)]],
               [(sign*a,b) for a,b in [(-2,9),(-7,4),(-2,-1)]]]
    elif name=='BACK':paths=[[(7,0),(-7,0)],[(-2,5),(-7,0),(-2,-5)]]
    elif name=='CLOSE':paths=[[(-4,-4),(4,4)],[(-4,4),(4,-4)]]
    elif name=='PLUS':paths=[[(-5,0),(5,0)],[(0,-5),(0,5)]]
    elif name=='MINUS':paths=[[(-5,0),(5,0)]]
    elif name=='SHADING':
        p.rectangle(cx-7*u,cy-7*u,14*u,14*u,BUTTON,7*u,color,1.3*u)
        paths=[[(0,6),(0,-6)],[(-3,4),(-3,-4)]]
    for path in paths:
        for a,b in zip(path,path[1:]):p.line((cx+a[0]*u,cy+a[1]*u),(cx+b[0]*u,cy+b[1]*u),color,1.5*u)


def build(s,region):
    e=s.editor;u=scale();w,h=region.width,region.height
    p=e.painter;p.begin(w,h);e.widgets=[];setup=s.stage in ('ORIENT','FIT');confirm=s.stage=='CONFIRM'
    def text(value,x,y,size=13,color=TEXT,max_width=None,center=False):
        if max_width is not None:value=shorten(value,max_width,size)
        if center:x-=measure(value,size)/2
        p.label(value,x,y,size,color)
    def button(key,value,box,selected=False,enabled=True,primary=False,size=13,icon_name=None,center=False):
        x,y,bw,bh=box;hover=enabled and e.hover==key
        fill=(PRIMARY_HOVER if hover else PRIMARY) if primary else (SELECT_HOVER if hover else SELECT) if selected else HOVER if hover else BUTTON
        edge=PRIMARY_HOVER if primary else (.27,.43,.46,1) if selected else BORDER
        foreground=(.065,.13,.15,1) if primary else TEXT
        if not enabled:
            fill=tuple(v*.76 for v in fill[:3])+(1,);foreground=(.41,.46,.51,1);edge=BUTTON
        p.rectangle(x,y,bw,bh,fill,7*u,edge,.7*u)
        if icon_name:icon(p,icon_name,box,foreground,u)
        else:
            blf.size(0,size*u);height=blf.dimensions(0,'Ag')[1]
            text(value,x+bw/2 if center else x+12*u,y+(bh-height)/2+1*u,size,foreground,bw-24*u,center)
        e.widgets.append({'key':key,'box':box,'enabled':enabled,'tooltip':describe(s,key,enabled)})

    p.rectangle(*e.boxes['TOP'].box,PANEL)
    text('Anime SDF Gen',20*u,h-27*u,18)
    primary_key='CANCEL_GENERATION' if s.busy else 'GENERATE' if confirm else 'NEXT'
    primary_text='Cancel generation' if s.busy else 'Generate & Finish' if confirm else 'Next Step  →'
    bw=min(230*u,w*.30);primary_x=w-16*u-bw;back_x=primary_x-46*u
    button(primary_key,primary_text,(primary_x,h-80*u,bw,42*u),primary=True,size=15,center=True)
    button('BACK','',(back_x,h-76*u,38*u,34*u),enabled=s.stage!='ORIENT' and not s.busy,icon_name='BACK')
    actions=[('UNDO','',36,bool(s.history.undo_stack)),('REDO','',36,bool(s.history.redo_stack)),
             ('DRAFT','Save draft & close',148,True),('CLOSE','Discard & close',130,True)]
    x=16*u
    for key,value,b,enabled in actions:
        if w<1040*u:value={'DRAFT':'Save & close','CLOSE':'Close'}.get(key,value);b=min(b,110)
        if x+b*u>back_x-12*u:break
        button(key,value,(x,h-77*u,b*u,34*u),enabled=(not s.busy and enabled) or key=='CLOSE',icon_name=key if key in ('UNDO','REDO') else None)
        x+=(b+7)*u

    for name in ('AUTHOR','PREVIEW'):
        if name not in e.boxes:continue
        x,y,vw,vh=e.boxes[name].box;top=y+vh
        p.rectangle(x,top-56*u,vw,56*u,PANEL)
        controls=0
        if not setup:
            focus_x=x+vw-12*u if confirm else x+vw-96*u
            if not confirm:
                button('FOCUS_'+name,'Split views' if e.focus==name else 'Focus',(focus_x,top-41*u,84*u,28*u),enabled=not s.busy,size=12,center=True)
            controls=(12 if confirm else 108)*u
            if name=='PREVIEW':
                compact=vw<370*u;flat_w=(34 if compact else 124)*u;flat_x=focus_x-flat_w-(0 if confirm else 8)*u
                button('FLAT','Flat mask' if s.flat else 'Shaded preview',(flat_x,top-41*u,flat_w,28*u),
                       selected=s.flat,enabled=not s.busy,size=12,icon_name='SHADING' if compact else None,center=True)
                controls+=flat_w+8*u
        if name=='AUTHOR' or e.focus=='PREVIEW' or confirm:
            number,guide={'ORIENT':('1 / 4','Orient the face to front view.'),
                          'FIT':('2 / 4','Place markers.'),'EDIT':('3 / 4','Adjust curves.'),
                          'CONFIRM':('4 / 4','Confirm.')}[s.stage]
            p.rectangle(x+16*u,top-41*u,44*u,25*u,SELECT,8*u)
            text(number,x+38*u,top-34*u,12,ACCENT,center=True)
            text(guide,x+76*u,top-34*u,17,TEXT,max(0,vw-76*u-max(controls,16*u)))
        else:text('Live shadow preview',x+18*u,top-33*u,13,MUTED,max(0,vw-18*u-controls))
    if 'DIVIDER' in e.boxes:
        d=e.boxes['DIVIDER'];p.rectangle(d.x,d.y,d.width,d.height,BG)
        p.rectangle(d.x+d.width/2,d.y,1,d.height,BORDER)
    p.flush()

    panel=e.boxes['PANEL'];px,py,pw,ph=panel.box;x=px+16*u;cw=pw-32*u
    p.rectangle(*panel.box,PANEL);p.flush()
    notice=s.error or s.seam_warning
    if e.warning_text!=notice:e.warning_text=notice;e.warning_scroll=0
    warning_lines=wrap(notice,cw-12*u) if notice else []
    footer=min(ph*.48,(len(warning_lines)*18+78)*u) if warning_lines else 0
    footer=int(footer)
    body=Rect(px,footer,pw,max(1,ph-footer));e.boxes['PANEL_BODY']=body
    e.boxes['WARNING']=Rect(px,0,pw,footer)
    e.warning_bounds=e.boxes['WARNING']
    old_scissor=gpu.state.scissor_get();gpu.state.scissor_test_set(True);gpu.state.scissor_set(*body.box)
    panel_start=len(e.widgets);scroll=max(0,e.panel_scroll);y=ph-29*u+scroll
    def heading(value):
        nonlocal y
        text(value,x,y,12,MUTED,cw);y-=19*u
    def row(items):
        nonlocal y
        width=(cw-6*u*(len(items)-1))/len(items)
        for i,item in enumerate(items):
            key,value,*options=item;selected=options[0] if options else False;enabled=options[1] if len(options)>1 else True
            button(key,value,(x+i*(width+6*u),y-31*u,width,32*u),selected,enabled and not s.busy)
        y-=39*u
    if confirm:
        destination=Path(bpy.path.abspath(s.project['settings']['output']))
        heading('Save location')
        row([('DESTINATION',str(destination.parent))]);y-=10*u
        heading('File name');row([('FILENAME',destination.name)]);y-=10*u
        heading('Texture resolution');resolution=s.project['settings']['resolution']
        row([('RESOLUTION',f'{resolution} × {resolution}')]);y-=15*u
        heading('Output packing · PNG 16-bit')
        for name, label in MAP_LABELS.items():
            text(label,x,y,13);y-=19*u
            for i, route in enumerate(OUTPUT_ROUTES):
                width=44*u if i<3 else cw-150*u
                button(f'PACK:{name}:{route}','Separate' if route=='SEPARATE' else route,
                       (x+i*50*u,y-31*u,width,32*u),
                       selected=s.project['settings']['packing'][name]==route,
                       enabled=not s.busy,size=12,center=True)
            y-=49*u
        y-=5*u
        heading('Files to generate')
        textures,sidecar=output_layout(s.project,destination)
        for texture in textures:
            for line in wrap(texture['path'].name,cw,12):text(line,x,y,12,TEXT);y-=18*u
            mapping=' · '.join(('Gray' if channel=='Y' else channel)+': '+MAP_LABELS[name]
                              for channel,name in texture['channels'].items())
            for line in wrap(mapping,cw,11):text(line,x,y,11,MUTED);y-=17*u
            y-=8*u
        for line in wrap(sidecar.name,cw,12):text(line,x,y,12,TEXT);y-=18*u
        y-=24*u;row([('FRAME','Frame face')])
    if setup:
        heading('Keyframes per sweep');count=s.project['authoring']['keyframe_count'];square=32*u;gap=8*u
        button('KEYFRAMES_LESS','',(x,y-31*u,square,32*u),enabled=count>2 and not s.busy,icon_name='MINUS')
        button('KEYFRAME_COUNT',str(count),(x+square+gap,y-31*u,cw-2*(square+gap),32*u),enabled=not s.busy,size=16,center=True)
        button('KEYFRAMES_MORE','',(x+cw-square,y-31*u,square,32*u),enabled=count<33 and not s.busy,icon_name='PLUS')
        y-=49*u
    if s.stage=='FIT':
        heading('Fitting markers')
        for name,value in (('nose','Nose'),('mouth','Mouth Center'),('chin','Chin')):row([('LANDMARK:'+name,value,s.landmark==name)])
        y-=10*u;heading('Starting preset')
        row([('PRESET_CLEAN','Clean Face',s.project['preset']=='CLEAN'),('PRESET_NOSE','Nose Accent',s.project['preset']=='NOSE')])
        row([('MIRROR','Mirror Full Sweep',s.project['mirror_sweeps'])]);y-=10*u
    if not confirm:
        heading('Reference & view');ref=s.project['authoring']['reference']
        row([('REF_NEUTRAL','Neutral',ref=='NEUTRAL'),('REF_MATERIAL','Materials',ref=='MATERIAL')])
        row([('FRAME','Frame face'),('SOURCE','Source / UV…')])
    if setup:row([('NAV_FRONT','Front'),('NAV_RIGHT','Right'),('NAV_TOP','Top')])
    elif not confirm:
        y-=10*u;heading(f'Shadow keyframes · {len(model.sweep(s.project,s.direction))}')
        row([('ADD_KEYFRAME','Add keyframe',False,len(model.sweep(s.project,s.direction))<33),('REMOVE_KEYFRAME','Remove',False,0<s.key_index<len(model.sweep(s.project,s.direction))-1)])
        row([('COPY_KEYFRAME','Copy previous keyframe',False,s.key_index>0)]);row([('MIRROR','Mirror Full Sweep',s.project['mirror_sweeps'])])
        y-=10*u;heading('Contours')
        for index,c in enumerate(s.keyframe['contours']):
            sign='+' if c['operation']=='ADD' else '−'
            row([('LAYER:'+str(index),('· ' if not c.get('enabled',True) else '')+sign+'  '+c['name'],index==s.contour)])
        row([('TRIANGLE','+  Add triangle')])
        if s.curve['closed']:
            row([('LIT','Lit area',s.curve['operation']=='REMOVE'),('SHADOW','Shadow area',s.curve['operation']=='ADD')])
            row([('DUPLICATE','Duplicate'),('DELETE_SHAPE','Delete')])
            row([('UP','Up',False,s.contour>1),('DOWN','Down',False,s.contour<len(s.keyframe['contours'])-1),('TOGGLE','Hide' if s.curve.get('enabled',True) else 'Show')])
            row([('TRANSFORM','Move / Rotate / Scale…')])
        y-=10*u;heading(f'Point {s.point+1}');point=s.curve['points'][s.point]
        row([('POINT',f"X {point['co'][0]:.4f}   Y {point['co'][1]:.4f}…")])
        row([('SMOOTH','Smooth',point['mode']=='AUTO'),('CORNER','Corner',point['mode']=='CORNER'),('FREE','Free',point['mode']=='FREE')])
        removable=len(s.curve['points'])>(3 if s.curve['closed'] else 2) and (s.curve['closed'] or s.point not in (0,len(s.curve['points'])-1))
        row([('INSERT_POINT','Insert'),('DELETE_POINT','Remove',False,removable)])
    extent=(ph-29*u)-(y-scroll);e.panel_scroll_max=max(0,extent-body.height+32*u);e.panel_scroll=min(e.panel_scroll,e.panel_scroll_max)
    for widget in e.widgets[panel_start:]:widget['clip']=body.box
    if e.panel_scroll_max:
        thumb=max(24*u,body.height*body.height/(body.height+e.panel_scroll_max))
        thumb_y=body.y+(body.height-thumb)*(1-e.panel_scroll/e.panel_scroll_max)
        p.rectangle(px+pw-5*u,thumb_y,3*u,thumb,MUTED,1.5*u)
    p.flush();gpu.state.scissor_set(px,py,pw,ph)
    if warning_lines:
        card=(px+12*u,12*u,pw-24*u,footer-18*u)
        p.rectangle(*card,(.15,.119,.111,1),8*u,(.30,.235,.20,1),.7*u)
        text('Needs attention',x+6*u,footer-30*u,12,WARN,cw-38*u)
        button('DISMISS_ERROR','',(px+pw-48*u,footer-38*u,24*u,24*u),icon_name='CLOSE')
        p.flush()
        message=Rect(round(x+6*u),round(24*u),round(cw-12*u),max(1,round(footer-71*u)))
        e.boxes['WARNING_TEXT']=message
        e.warning_scroll_max=max(0,len(warning_lines)*18*u-message.height)
        e.warning_scroll=min(e.warning_scroll,e.warning_scroll_max)
        gpu.state.scissor_set(*message.box)
        for i,line in enumerate(warning_lines):text(line,message.x,message.y+message.height-14*u-i*18*u+e.warning_scroll,12.5,WARN)
        p.flush();gpu.state.scissor_set(px,py,pw,ph)
        if e.warning_scroll_max:
            thumb=max(15*u,message.height**2/(message.height+e.warning_scroll_max))
            p.rectangle(px+pw-20*u,message.y+(message.height-thumb)*(1-e.warning_scroll/e.warning_scroll_max),2*u,thumb,WARN,u)
            p.flush()
    else:e.warning_scroll_max=0
    gpu.state.scissor_set(*old_scissor);gpu.state.scissor_test_set(False)

    if not setup:
        shelf=e.boxes['SHELF'];sx,sy,sw,sh=shelf.box;p.rectangle(*shelf.box,BG)
        direction,progress=model.rotation_sample(s.rotation)
        if not confirm:
            label_width=145*u;start_x=label_width+16*u
            columns=max(2,int((sw-start_x-16*u)/(48*u)))
            max_count=max(len(model.sweep(s.project,d)) for d in model.SWEEP_LABELS)
            s.keyframe_scroll=max(0,min(getattr(s,'keyframe_scroll',0),max(0,max_count-columns)))
            for row_index,(row_direction,title) in enumerate(model.SWEEP_LABELS.items()):
                frames=model.sweep(s.project,row_direction)
                start=min(s.keyframe_scroll,max(0,len(frames)-columns))
                shown=list(enumerate(frames))[start:start+columns];bw=(sw-start_x-16*u)/len(shown)
                row_y=sh-(34+33*row_index)*u
                active=(direction if s.orbit_preview else s.direction)==row_direction
                text(title,16*u,row_y+7*u,13,ACCENT if active else MUTED,label_width-8*u)
                nearest=min(range(len(frames)),key=lambda i:abs(frames[i]['progress']-progress))
                for column,(index,frame) in enumerate(shown):
                    chosen=active and index==(nearest if s.orbit_preview else s.key_index)
                    button(f'KEYFRAME:{row_direction}:{index}',str(index+1),
                           (start_x+column*bw,row_y,bw-6*u,25*u),chosen,not s.busy,size=12,center=True)
        text(f'Light rotation · {s.rotation:.0f}°',16*u,67*u,12,MUTED)
        button('PLAY','Pause' if s.playing else 'Play 360°',(16*u,32*u,95*u,26*u),enabled=not s.busy,size=12,center=True)
        slider=(130*u,34*u,max(1,sw-152*u),22*u);e.boxes['SLIDER']=slider;x,y,ww,hh=slider
        p.rectangle(x,y+hh/2-u,ww,2*u,BORDER,u)
        p.rectangle(x+s.rotation/360*ww-5*u,y+hh/2-5*u,10*u,10*u,ACCENT,5*u)
        for fraction,caption in ((0,'Front'),(.25,'Character left'),(.5,'Back'),(.75,'Character right'),(1,'Front')):
            tx=x+fraction*ww
            if fraction==1:tx-=measure(caption,10)
            text(caption,tx,y-13*u,10,MUTED,center=0<fraction<1)
        if s.busy:text(s.message,16*u,7*u,11,MUTED,sw-32*u)
        p.flush()
    draw_tooltip(s,region)


def draw_tooltip(s,region):
    e=s.editor;e.tooltip_box=None
    if not e.tooltip_ready or not e.hover or s.dragging or e.navigation.running():return
    widget=next((item for item in e.widgets if item['key']==e.hover),None)
    if not widget:return
    x,y,w,h=widget['box'];mx,my=e.hover_pos
    def inside(box):return box[0]<=mx<box[0]+box[2] and box[1]<=my<box[1]+box[3]
    if not inside(widget['box']) or ('clip' in widget and not inside(widget['clip'])):return
    u=scale();tip=widget['tooltip'];width=min(320*u,region.width-24*u)
    body=wrap(tip['body'],width-28*u,12);reason=wrap(tip['reason'],width-28*u,12) if tip['reason'] else []
    height=(48+18*(len(body)+len(reason))+(8 if reason else 0))*u
    tx=max(12*u,min(x,region.width-width-12*u));ty=y-height-10*u
    if ty<12*u:ty=y+h+10*u
    ty=max(12*u,min(ty,region.height-height-12*u));e.tooltip_box=(tx,ty,width,height)
    p=e.painter;p.rectangle(tx,ty-3*u,width,height,(.015,.02,.026,.4),8*u)
    p.rectangle(tx,ty,width,height,(.105,.125,.153,1),8*u,(.26,.32,.38,1),.8*u)
    p.label(shorten(tip['title'],width-28*u,13),tx+14*u,ty+height-24*u,13,TEXT)
    yy=ty+height-45*u
    for line in body:p.label(line,tx+14*u,yy,12,(.71,.77,.83,1));yy-=18*u
    if reason:
        yy-=8*u
        for line in reason:p.label(line,tx+14*u,yy,12,WARN);yy-=18*u
    p.flush()


def dispatch(s,key):
    ops=bpy.ops.anime_sdf_gen
    if key.startswith('PACK:'):
        _,name,route=key.split(':');return ops.packing(map_name=name,route=route)
    if key in ('RESOLUTION','FILENAME','SOURCE','KEYFRAME_COUNT','POINT'):
        return ops.settings('INVOKE_DEFAULT',section=key)
    if key=='DESTINATION':return ops.destination('INVOKE_DEFAULT')
    if key=='DRAFT':return ops.save_draft('INVOKE_DEFAULT')
    if key=='CLOSE':return ops.close()
    if key=='GENERATE':return ops.generate('INVOKE_DEFAULT')
    if key=='CANCEL_GENERATION':return ops.cancel_generation()
    if key=='TRANSFORM':return ops.transform('INVOKE_DEFAULT')
    if key.startswith('NAV_'):
        return s.editor.navigation.command('AUTHOR','view_axis',type=key[4:])
    if key=='DISMISS_ERROR':s.error=s.seam_warning='';s.redraw();return
    if key.startswith('PRESET_'):
        s.push_history();s.project['preset']=key[7:];s.sync_ui();s.redraw();s.draft_due=.1;return
    if key.startswith('LAYER:'):return ops.layer(index=int(key.split(':')[1]))
    if key.startswith('KEYFRAME:'):
        _,direction,index=key.split(':');return ops.keyframe(direction=direction,index=int(index))
    if key.startswith('LANDMARK:'):return ops.landmark(name=key.split(':')[1])
    props=bpy.context.window_manager.anime_sdf_gen
    if key.startswith('REF_'):props.reference=key[4:];return
    if key=='FLAT':props.flat=not props.flat;return
    if key in ('LIT','SHADOW'):props.layer_operation='REMOVE' if key=='LIT' else 'ADD';return
    if key in ('SMOOTH','CORNER','FREE'):props.handle_mode='AUTO' if key=='SMOOTH' else key;return
    return ops.action(action=key)
