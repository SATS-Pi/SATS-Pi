import asyncio, subprocess, os, sys
from playwright.async_api import async_playwright
SC=[("A",0,6),("B",6,11),("C",11,21),("D",21,28),("E",28,36),("F",36,46),("G",46,52),("H",52,58),("I",58,64)]
FPS=30
async def do(name,a,b):
    final=f"/home/claude/video/scenes/{name}.mp4"; tmp=f"/home/claude/video/scenes/{name}.part.mp4"
    n=int((b-a)*FPS)
    ff=subprocess.Popen(["ffmpeg","-y","-loglevel","error","-f","image2pipe","-framerate",str(FPS),"-c:v","mjpeg","-i","-",
        "-c:v","libx264","-crf","18","-preset","veryfast","-pix_fmt","yuv420p","-r",str(FPS),tmp],stdin=subprocess.PIPE)
    async with async_playwright() as p:
        br=await p.chromium.launch()
        pg=await br.new_page(viewport={"width":1280,"height":720},device_scale_factor=1.5)
        await pg.goto("file:///home/claude/video/film.html"); await pg.wait_for_function("window.READY===true")
        for i in range(n):
            await pg.evaluate(f"render({a+i/FPS})")
            ff.stdin.write(await pg.screenshot(type="jpeg",quality=92))
        await br.close()
    ff.stdin.close()
    if ff.wait()==0: os.rename(tmp,final); print("done",name,flush=True)
    else: print("FAIL",name,flush=True)
async def worker(q):
    for s in q: await do(*s)
async def main():
    await asyncio.gather(worker([SC[i] for i in (0,2,4,6,8)]),worker([SC[i] for i in (1,3,5,7)]))
asyncio.run(main())
