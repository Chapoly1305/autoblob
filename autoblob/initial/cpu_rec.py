#from cpu_rec import TrainingData, FileAnalysis
import logging
import sys
import os
import importlib.util
l = logging.getLogger("autoblob.cpu_rec")

package_directory = os.path.dirname(os.path.abspath(__file__))

paths = ["../lib/cpu_rec/cpu_rec.py",
         os.path.join(package_directory,"../../lib/cpu_rec/cpu_rec.py")]

def find_cpu_rec():
    for filename in paths:
        try:
            abs_path = os.path.abspath(filename)
            if not os.path.exists(abs_path):
                continue
            name = os.path.splitext(os.path.basename(abs_path))[0]
            l.debug(f"Loading {name} from {abs_path}")
            spec = importlib.util.spec_from_file_location(name, abs_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            l.debug('After: %s in sys.modules == %s' % (name, name in sys.modules))
            return mod
        except:
            pass
            #l.exception(filename)
    else:
        l.warning("cpu_rec not found!")
        return None

def cpu_rec_initial(stream):
    cpu_rec = find_cpu_rec()
    if not cpu_rec:
        return (None, None, None)
    l.debug("cpu_rec analysis starting...")
    # TODO: Don't do that
    l.debug("Loading file...")
    data = stream.read()
    stream.seek(0)

    l.debug("Loading training data...")
    t = cpu_rec.TrainingData()
    t.read_corpus()
    p = cpu_rec.FileAnalysis(t)
    l.debug('Beginning full-file analysis...')
    d = cpu_rec.TrainingData.unpack_file(data)
    res, r2, r3 = p.deduce(d)
    l.debug('%-15s%-10s' % ('full(%#x)' % len(d), res))
    l.debug("                   %s", r2[:4])
    l.debug("                   %s", r3[:4])
    l.debug("Looking for a text section, if possible...")
    # Text section, if possible
    try:
        d_txt = cpu_rec.TrainingData.extract_section(d, section='text')
        if len(d) != len(d_txt):
            res, r2, r3 = p.deduce(d_txt)
            l.debug('%-15s%-10s' % ('text(%#x)' % len(d_txt), res))
        else:
            l.debug('%-15s%-10s' % ('', ''))
    except:
        l.exception("Text extraction analysis failed.  Probably elfesteem is messed up.")
    l.debug("Performing sliding window analysis...")
    _, cpu, sz, cnt, _ = p.sliding_window(d)
    l.debug('%-20s%-10s' % ('chunk(%#x;%s)'%(2*sz*cnt,cnt), cpu))
    if res and cpu and res == cpu:
        return (res.lower(), None, None)
    if cpu:
        return (cpu.lower(), None, None)
    if res:
        return (res.lower(), None, None)
    return (None, None, None)

if __name__ == '__main__':
    l.setLevel(logging.DEBUG)
    with open(sys.argv[1], 'rb') as f:
        print(cpu_rec_initial(f)[0])
        
