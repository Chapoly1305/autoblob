# AutoBlob

**Automatic Blob Loading for CLE**

AutoBlob is an intelligent binary loader for [CLE](https://github.com/angr/cle) (the binary loader component of the [angr](https://angr.io/) binary analysis framework). It automatically detects architecture, base address, and entry point for raw binary blobs that lack headers or metadata—such as firmware images, embedded binaries, and memory dumps.

## The Problem

Traditional binary loaders rely on file format headers (ELF, PE, Mach-O) to determine:
- What CPU architecture the code is compiled for
- Where in memory the binary should be loaded (base address)
- Where execution should start (entry point)

Raw binary blobs lack these headers, making them difficult to analyze. AutoBlob solves this by using a chain of heuristic detectors to automatically discover this information.

## How It Works

AutoBlob extends CLE's `Blob` backend and runs multiple detection methods in sequence until it successfully identifies the binary's properties:

### Detection Chain

1. **Marvell Firmware Detector**
   - Searches for "MRVL" signature in firmware headers
   - Extracts entry point, stack pointer, and base address from header structure
   - Identifies ARM Cortex-M architecture

2. **ARM IVT (Interrupt Vector Table) Finder**
   - Examines first 256 bytes for valid ARM IVT structure
   - Validates stack pointer range (0x1FFF0000 - 0x20100000)
   - Reads reset vector for entry point
   - Supports both little-endian and big-endian ARM
   - Estimates base address using minimum vector address approach (analyzes all IVT entries to find lowest code address, then aligns to 4KB boundary)

3. **CubScout Architecture Detector**
   - Scans binary for function prologs and epilogs using regex patterns
   - Matches against all architectures in archinfo (70+ CPU types)
   - Validates matches using instruction alignment
   - Uses voting system to determine most likely architecture
   - Works across wide range of CPU families

4. **cpu_rec (Airbus SecLab)**
   - Employs statistical/machine learning approach for architecture identification
   - Analyzes instruction byte patterns against trained corpus of 70+ architectures
   - Uses compressed training data from real-world binaries
   - Performs full-file analysis, text section extraction, and sliding window analysis
   - Serves as robust fallback when other methods fail
   - More details: https://github.com/airbus-seclab/cpu_rec

Each detector returns a tuple of `(architecture, base_address, entry_point)`, with `None` for values it cannot determine. AutoBlob stops once all three values are found, or provides sensible defaults (base=0, entry=0) if detection fails.

## Installation

### Prerequisites
- Python 3.x
- angr framework (includes `cle` and `archinfo`)

### Install from source

```bash
# Clone the repository
git clone https://github.com/subwire/autoblob.git
cd autoblob

# Initialize the cpu_rec submodule
git submodule update --init --recursive

# Install
pip install -e .
```

Or install the dependencies manually:
```bash
pip install cle archinfo
```

## Usage

### As a CLE Backend (Automatic)

AutoBlob automatically registers itself as a CLE backend when imported. CLE will attempt to use AutoBlob when it cannot identify a binary's format.

```python
import cle
from autoblob import AutoBlob

# CLE will automatically try AutoBlob for unrecognized formats
loader = cle.Loader('firmware.bin')
```

### Standalone Testing

Test AutoBlob's detection capabilities on a binary:

```bash
python -m autoblob.autoblob firmware.bin
```

This will print the detected architecture, base address, and entry point.

### In angr Projects

```python
import angr
from autoblob import AutoBlob

# angr will use AutoBlob automatically for raw binaries
project = angr.Project('firmware.bin', auto_load_libs=False)

# Access detected information
print(f"Architecture: {project.arch}")
print(f"Entry point: {hex(project.entry)}")
```

### Manual Usage

```python
import cle
from autoblob import AutoBlob

# Load a raw binary blob with AutoBlob
loader = cle.Loader('firmware.bin',
                    main_opts={
                        'backend': 'autoblob',
                        'arch': 'arm'  # Optional: hint the architecture
                    })

# Or let CLE auto-detect
with open('firmware.bin', 'rb') as f:
    if AutoBlob.is_compatible(f):
        print("AutoBlob can handle this binary!")
```

## Supported Architectures

Through the combination of CubScout and cpu_rec, AutoBlob can detect 70+ CPU architectures including:

- **ARM**: ARM64, ARMel, ARMeb, ARMhf, ARM Cortex-M
- **x86**: x86, x86-64
- **MIPS**: MIPSel, MIPSeb, MIPS16
- **PowerPC**: PPCel, PPCeb
- **RISC architectures**: RISC-V, SPARC, Alpha, HP-PA
- **Embedded**: MSP430, AVR, PIC (10/16/18/24), STM8, 8051, H8-300
- **DSP**: TMS320C2x, TMS320C6x
- **Historical/Exotic**: VAX, PDP-11, Cray, MMIX, i860, M88k, and many more

See the [cpu_rec README](lib/cpu_rec/README.md) for the complete list.

## Architecture

```
autoblob/
├── autoblob.py          # Main AutoBlob class (extends CLE Blob backend)
├── __init__.py          # Package initialization
└── initial/             # Detection methods
    ├── __init__.py      # Detection chain orchestration
    ├── arm_ivt_finder.py         # ARM interrupt vector table detection
    ├── marvell_fw_finder.py      # Marvell firmware header detection
    ├── cubscout.py               # Function prolog/epilog pattern matching
    └── cpu_rec.py                # Interface to Airbus SecLab cpu_rec

lib/
└── cpu_rec/             # Git submodule: Airbus SecLab cpu_rec library
```

## Extensibility

Adding new detection methods is straightforward:

1. Create a new detector function in `autoblob/initial/`:
   ```python
   def detect_my_format(stream):
       # Your detection logic here
       return (arch, base_addr, entry_point)  # or (None, None, None)
   ```

2. Add it to the detection chain in `autoblob/initial/__init__.py`:
   ```python
   initial_detectors = [
       detect_marvell_fw,
       detect_arm_ivt,
       detect_my_format,  # Your new detector
       cubscout_detect_arch,
       cpu_rec_initial
   ]
   ```

Detectors run in order and should return quickly if they cannot handle a binary.

## Limitations

- **Detection accuracy**: Heuristic-based detection may misidentify heavily obfuscated or encrypted binaries
- **Performance**: cpu_rec analysis can be slow on large files (expect ~1 minute per MB)
- **False positives**: Some data sections may be misidentified as code (especially with IA-64)
- **Base address**: Estimated base addresses are educated guesses and may need manual adjustment
- **Entry point**: May default to 0 if no clear entry point is found

For best results:
- Provide hints when possible (architecture, base address, entry point)
- Use on raw firmware extracted from devices, not encrypted or compressed images
- Validate detection results before conducting analysis

## Use Cases

- **Firmware Analysis**: Load and analyze router, IoT, or embedded device firmware
- **Memory Dump Analysis**: Analyze raw memory dumps from physical devices
- **Malware Analysis**: Examine shellcode or memory-resident malware
- **Reverse Engineering**: Analyze binaries with stripped or missing headers
- **CTF Challenges**: Quickly identify mystery binaries in capture-the-flag competitions

## Development

Created by Eric Gustafson ([@subwire](https://github.com/subwire))

Initial release: October 2017

### Recent Updates
- Python 3 compatibility
- Updated for latest CLE API changes
- ARM Cortex-M support
- Marvell firmware detection
- Improved ARM IVT detection

## Contributing

Contributions welcome! Areas for improvement:
- Additional format detectors (add to `autoblob/initial/`)
- Performance optimizations
- Better base address heuristics
- Support for additional firmware formats

## License

[License information not specified in repository]

## See Also

- [angr](https://angr.io/) - Binary analysis framework
- [CLE](https://github.com/angr/cle) - Binary loader for angr
- [cpu_rec](https://github.com/airbus-seclab/cpu_rec) - CPU architecture recognition tool
- [archinfo](https://github.com/angr/archinfo) - Architecture information database
