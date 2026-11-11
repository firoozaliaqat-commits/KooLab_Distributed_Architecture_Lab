"""Time-limited educational CPU load generator. Run ONLY inside own lab VM."""
import multiprocessing as mp, os, signal, sys, time

def work(deadline):
    v=17
    while time.monotonic()<deadline:
        for _ in range(20000): v=(v*1664525+1013904223)%4294967296

def main():
    duration=min(max(int(sys.argv[1]),1),900)
    workers=min(max(int(sys.argv[2]),1),2)
    deadline=time.monotonic()+duration
    children=[mp.Process(target=work,args=(deadline,)) for _ in range(workers)]
    def stop(*_):
        for child in children:
            if child.is_alive(): child.terminate()
        for child in children:child.join(timeout=1)
        sys.exit(0)
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    for child in children:child.start()
    for child in children:child.join(timeout=duration+3)
    stop()

if __name__=='__main__':main()
