import numpy as np
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing, Group, Line, PolyLine, Rect, String, Circle, Polygon
from reportlab.lib import colors

BLUE = colors.HexColor("#235789")
RED = colors.HexColor("#b14436")
TEAL = colors.HexColor("#317d73")
INK = colors.HexColor("#263447")
GRAY = colors.HexColor("#dce4eb")


def label(group,x,y,text,size=8,anchor="start",color=INK):
    group.add(String(x,y,text,fontName="Helvetica",fontSize=size,textAnchor=anchor,fillColor=color))


def chart(title, xname, yname, xlim, ylim, series, guides=(), band=None):
    g=Group()
    x0,y0,w,h=49,38,173,120
    xx=lambda x:x0+w*(x-xlim[0])/(xlim[1]-xlim[0])
    yy=lambda y:y0+h*(y-ylim[0])/(ylim[1]-ylim[0])
    label(g,x0,174,title,9)
    label(g,x0,161,yname,7)
    for x in np.linspace(*xlim,5):
        g.add(Line(xx(x),y0,xx(x),y0+h,strokeColor=GRAY,strokeWidth=.45))
        label(g,xx(x),y0-12,f"{x:.3g}",7,"middle")
    for y in np.linspace(*ylim,5):
        g.add(Line(x0,yy(y),x0+w,yy(y),strokeColor=GRAY,strokeWidth=.45))
        label(g,x0-4,yy(y)-2.5,f"{y:.3g}",7,"end")
    g.add(Rect(x0,y0,w,h,fillColor=None,strokeColor=INK,strokeWidth=.6))
    label(g,x0+w/2,12,xname,8,"middle")
    if band is not None:
        x,lo,hi=band
        coords=list(zip(map(xx,x),map(yy,lo)))+list(zip(map(xx,x[::-1]),map(yy,hi[::-1])))
        g.add(Polygon([t for pair in coords for t in pair],fillColor=colors.HexColor("#d7e8f5"),strokeColor=None))
    for direction,val in guides:
        if direction=="x":
            g.add(Line(xx(val),y0,xx(val),y0+h,strokeColor=GRAY,strokeWidth=1.3))
        else:
            g.add(Line(x0,yy(val),x0+w,yy(val),strokeColor=GRAY,strokeWidth=1.3))
    for x,y,c,mode in series:
        coords=list(zip(map(xx,x),map(yy,y)))
        if mode in ("line","both"):
            g.add(PolyLine([t for pair in coords for t in pair],strokeColor=c,strokeWidth=1.25))
        if mode in ("dots","both"):
            for a,b in coords:
                g.add(Circle(a,b,1.65,fillColor=c,strokeColor=None))
    return g


def maps(title, values, limits, marks=()):
    g=Group()
    x0,y0,cell=60,31,12.2
    label(g,x0,174,title,9)
    for r in range(10):
        for c in range(10):
            v=float(np.clip(values[r,c]/limits,-1,1))
            end=BLUE if v<0 else RED
            bg=colors.Color(*[1-abs(v)*(1-k) for k in (end.red,end.green,end.blue)])
            g.add(Rect(x0+c*cell,y0+r*cell,cell,cell,fillColor=bg,strokeColor=None))
    g.add(Rect(x0,y0,10*cell,10*cell,fillColor=None,strokeColor=INK,strokeWidth=.6))
    for c,r in marks:
        g.add(Circle(x0+(c+.5)*cell,y0+(r+.5)*cell,3,strokeColor=INK,fillColor=None))
    for i in [0,3,6,9]:
        s=f"{-2.7+.6*i:.1f}"
        label(g,x0+(i+.5)*cell,y0-10,s,7,"middle")
        label(g,x0-4,y0+(i+.5)*cell-2,s,7,"end")
    label(g,x0+61,5,"x (probe pitches)",8,"middle")
    label(g,4,155,"y (pitch)",7)
    bar_x=x0+126
    for i,v in enumerate(np.linspace(-1,1,30)):
        end=BLUE if v<0 else RED
        bg=colors.Color(*[1-abs(v)*(1-k) for k in (end.red,end.green,end.blue)])
        g.add(Rect(bar_x,y0+i*4,7,4,fillColor=bg,strokeColor=None))
    for y,v in [(y0,-limits),(y0+60,0),(y0+116,limits)]:
        label(g,bar_x+10,y,f"{v:.3g}",7)
    return g


def panels(*groups):
    d=Drawing(480,189*(1+(len(groups)-1)//2))
    for i,g in enumerate(groups):
        g.translate(238*(i%2),189*((len(groups)-1)//2-i//2))
        d.add(g)
    return d


def make_figures(p,r,m):
    no, ye = p["nb"]/1e12,p["nf"]/1e12
    factor = r["L1"]["correction_factor"]
    l1=panels(
        chart("A  Carrier counts","Fermi level (eV)","Density (10^12 cm^-2)",(.025,.255),(0,5),
              [(p["sweep"],no,BLUE,"both"),(p["sweep"],ye,TEAL,"both")]),
        chart("B  Counting correction","Fermi level (eV)","Band-edge / Fermi count",(0,.25),(0,7),
              [(p["smooth_ef"],p["smooth_ratio"],BLUE,"line"),([m["ef_op"]],[factor],RED,"dots"),
               (m["crossings"],[2,4],TEAL,"dots")],guides=[("y",2),("y",4)]))
    xy=p["measured"]; curve=p["models"][int(p["selected"])]; idx=p["indices"]
    scaled_h=p["scans"][:,:,0]/np.max(np.abs(p["scans"][:,:,0].mean(axis=1)))
    l2=panels(
        chart("A  Signed Hall repeats","Measurement index","Hall coefficient / peak",(idx.min(),idx.max()),(-1.12,1.12),
              [(idx,scaled_h[:,j],c,"dots") for j,c in enumerate([BLUE,TEAL,RED])],
              guides=[("y",0),("x",np.mean(m["brackets"][0]))]),
        chart("B  Curve fit in paired space","Normalized Hall coefficient","Normalized sheet resistance",(-1.1,1.1),(0,1.08),
              [(curve[:,0],curve[:,1],BLUE,"line"),(xy[:,0],xy[:,1],RED,"dots")]),
        chart("C  Inferred Fermi trajectory","Measurement index","Fermi level (eV)",(idx.min(),idx.max()),(-.08,.16),
              [(idx,p["trajectory"],BLUE,"line")],band=(idx,p["ef_lo"],p["ef_hi"]),guides=[("y",0)]),
        chart("D  Gap scan","Candidate gap (kBT)","Normalized RMS residual",(0,8),(0,float(max(p["rms"])*1.08)),
              [(p["gaps"],p["rms"],BLUE,"both")],guides=[("y",.85*m["cone_rms"])]))
    marks=[(int((f["x"]+2.7)/.6+.5),int((f["y"]+2.7)/.6+.5)) for f in r["L3"]["features"]]
    l3=panels(
        maps("A  Relative conductivity deviation",p["map"],.02,marks),
        maps("B  Central point response",p["responses"][0],float(np.max(p["responses"][0])),[(5,5)]),
        chart("C  Regularization tradeoff","log10 roughness norm","log10 residual norm",(-1.4,-1.27),(-6,-2),
              [(np.log10(p["roughness"]),np.log10(p["residual"]),BLUE,"both"),
               (np.log10(p["roughness"][2:3]),np.log10(p["residual"][2:3]),RED,"dots")]),
        chart("D  Forward matrix spectrum","Singular value index","log10 singular value",(1,100),(-17,1),
              [(np.arange(1,101),np.log10(p["singular"]),BLUE,"line")]))
    overlay=panels(*[
        chart(title,"Fermi level (eV)",ylabel,(float(p["ef"].min()),float(p["ef"].max())),lim,
              [(p["ef"],curve[:,j],BLUE,"line"),(p["trajectory"],xy[:,j],RED,"dots")])
        for j,title,ylabel,lim in [(0,"A  Hall channel","Normalized Hall coefficient",(-1.1,1.1)),
                                     (1,"B  Resistance channel","Normalized sheet resistance",(0,1.08))]])
    return {"L1_carrier_count":l1,"L2_inversion":l2,"L3_reconstruction":l3,"L2_channel_overlays":overlay}


def write_figures(out,p,r,m):
    for name,d in make_figures(p,r,m).items():
        renderPDF.drawToFile(d,str(out/f"{name}.pdf"))
