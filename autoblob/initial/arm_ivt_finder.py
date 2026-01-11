import logging
import struct
import archinfo
l = logging.getLogger("autoblob")

# Common flash address ranges for ARM Cortex-M microcontrollers
MIN_FLASH_ADDR = 0x00000000
MAX_FLASH_ADDR = 0x20000000  # Below SRAM region

# SRAM address range for stack pointer validation
MIN_ARM_SP = 0x1FFF0000
MAX_ARM_SP = 0x20100000


def _extract_code_vectors(ivt_data, endness):
    """
    Extract valid code addresses from the IVT.

    :param ivt_data: Raw IVT bytes (at least 256 bytes for 64 vectors)
    :param endness: '<' for little-endian, '>' for big-endian
    :return: List of code addresses (with Thumb bit cleared)
    """
    fmt = endness + '64I'
    vectors = struct.unpack(fmt, ivt_data[:256])

    code_addrs = []
    # Skip index 0 (SP), and reserved entries that may contain non-code values
    # Indices: 1=Reset, 2=NMI, 3=HardFault, ..., 15=SysTick, 16+=IRQs
    reserved_indices = {0, 7, 8, 9, 10, 13}  # SP and reserved slots

    for i, v in enumerate(vectors[:48]):  # First 48 vectors
        if i in reserved_indices:
            continue
        # Check for Thumb bit (indicates code address) and valid flash range
        if (v & 1) and MIN_FLASH_ADDR < v < MAX_FLASH_ADDR:
            code_addrs.append(v & ~1)  # Clear Thumb bit

    return code_addrs


def _compute_base_from_vectors(code_addrs):
    """
    Compute base address from code vector addresses.

    The base address must be <= min(code_addrs) since all vectors
    must point within the loaded binary.

    :param code_addrs: List of code addresses from IVT
    :return: Estimated base address, aligned to 0x1000
    """
    if not code_addrs:
        return None

    min_addr = min(code_addrs)
    # Align down to 4KB boundary (common flash sector size)
    base = min_addr & 0xFFFFF000
    return base


def detect_arm_ivt(stream):
    """
    Detect ARM Cortex-M IVT and estimate base address.

    Uses the minimum vector address approach: analyzes all IVT entries
    to find the lowest code address, which provides an upper bound for
    the base address.

    :param stream: File stream to analyze
    :type stream: file
    :return: Tuple of (arch, base_address, entry_point) or (None, None, None)
    """
    try:
        # Read enough for full IVT (64 vectors * 4 bytes = 256 bytes)
        ivt_data = stream.read(256)
        if len(ivt_data) < 256:
            return (None, None, None)

        # Check SP value to determine endianness
        maybe_le_sp = struct.unpack('<I', ivt_data[:4])[0]
        maybe_be_sp = struct.unpack('>I', ivt_data[:4])[0]

        if MIN_ARM_SP < maybe_le_sp < MAX_ARM_SP:
            endness = '<'
            maybe_arch = archinfo.ArchARMCortexM(endness=archinfo.Endness.LE)
            l.debug("Found possible Little-Endian ARM IVT with initial SP %#08x" % maybe_le_sp)
        elif MIN_ARM_SP < maybe_be_sp < MAX_ARM_SP:
            endness = '>'
            maybe_arch = archinfo.ArchARM(endness=archinfo.Endness.BE)
            l.debug("Found possible Big-Endian ARM IVT with initial SP %#08x" % maybe_be_sp)
        else:
            return (None, None, None)

        # Extract entry point (reset vector)
        maybe_entry = struct.unpack(endness + 'I', ivt_data[4:8])[0]
        l.debug("Reset vector at %#08x" % maybe_entry)

        # Extract all code vectors and compute base from minimum
        code_addrs = _extract_code_vectors(ivt_data, endness)
        l.debug("Found %d valid code vectors" % len(code_addrs))

        if code_addrs:
            min_vector = min(code_addrs)
            max_vector = max(code_addrs)
            l.debug("Vector address range: %#08x - %#08x" % (min_vector, max_vector))
            maybe_base = _compute_base_from_vectors(code_addrs)
        else:
            # Fallback to old heuristic if no valid vectors found
            l.warning("No valid code vectors found, falling back to reset vector mask")
            maybe_base = maybe_entry & 0xFFFF0000

        l.debug("Estimated base address at %#08x" % maybe_base)
        return maybe_arch, maybe_base, maybe_entry

    except Exception:
        l.exception("Error detecting ARM IVT")
        return (None, None, None)
    finally:
        stream.seek(0)
