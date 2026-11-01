import sys,glob
from PIL import Image, ImageDraw
d=sys.argv[1]; fs=sorted(glob.glob(d+'/f*.png')); cols=int(sys.argv[2]) if len(sys.argv)>2 else 2
ims=[Image.open(f) for f in fs]; w,h=ims[0].size
rows=(len(ims)+cols-1)//cols
S=Image.new('RGB',(w*cols,h*rows),'black')
for i,(im,f) in enumerate(zip(ims,fs)):
  S.paste(im,((i%cols)*w,(i//cols)*h)); ImageDraw.Draw(S).text(((i%cols)*w+8,(i//cols)*h+8),f.split('/')[-1],fill='yellow')
S.save(d+'/sheet.jpg',quality=88); print(S.size)
