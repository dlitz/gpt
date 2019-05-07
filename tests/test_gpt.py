import pytest
import os


def load_sample_data(name):
    path = os.path.join(os.path.dirname(__file__),
                        'sample-data', '%s.bin' % (name,))
    with open(path, 'rb') as f:
        return f.read()


def entries_range(h):
    start = h.partition_entry_lba * 0x200
    length = h.number_of_partition_entries * h.size_of_partition_entry
    end = start + length
    return start, end


def test_roundtrip_mbr():
    import gpt
    sample = load_sample_data('disk1')
    raw1 = sample[:0x200]
    m = gpt.decode_mbr(raw1)
    assert m.is_valid()
    raw2 = gpt.encode_mbr(m)
    assert raw1 == raw2


def test_roundtrip_gpt_header():
    import gpt
    sample = load_sample_data('disk1')
    raw1 = sample[0x200:0x400]
    h = gpt.decode_gpt_header(raw1)
    assert h.header_size == 92, "expected header size 92"
    raw2 = gpt.encode_gpt_header(h)
    assert raw1[:h.header_size] == raw2


def test_roundtrip_gpt_partition_entry_array():
    import gpt
    sample = load_sample_data('disk1')
    h = gpt.decode_gpt_header(sample[0x200:0x400])

    start, end = entries_range(h)

    decoded_entries = gpt.decode_gpt_partition_entry_array(
        sample[start:end],
        h.size_of_partition_entry,
        h.number_of_partition_entries)

    reencoded_entries = gpt.encode_gpt_partition_entry_array(
        decoded_entries,
        h.size_of_partition_entry,
        h.number_of_partition_entries)

    assert sample[start:end] == reencoded_entries


def test_merge():
    import gpt

    sample1 = load_sample_data('disk1')
    sample2 = load_sample_data('disk2')
    sample_merged = load_sample_data('merged')

    h1 = gpt.decode_gpt_header(sample1[0x200:0x400])
    h2 = gpt.decode_gpt_header(sample2[0x200:0x400])

    start1, end1 = entries_range(h1)
    start2, end2 = entries_range(h2)

    decoded_entries1 = gpt.decode_gpt_partition_entry_array(
        sample1[start1:end1],
        h1.size_of_partition_entry,
        h1.number_of_partition_entries)

    decoded_entries2 = gpt.decode_gpt_partition_entry_array(
        sample2[start2:end2],
        h2.size_of_partition_entry,
        h2.number_of_partition_entries)

    # Copy disk2 partition table
    merged_h = gpt.decode_gpt_header(sample2[0x200:0x400])
    merged_entries = list(decoded_entries2)

    # Copy partitions 1-4 from disk1
    merged_entries[0:4] = decoded_entries1[0:4]
    merged_entries_raw = gpt.encode_gpt_partition_entry_array(
        merged_entries,
        merged_h.size_of_partition_entry,
        merged_h.number_of_partition_entries)

    # Update crc32 values
    merged_h.partition_entry_array_crc32 = gpt.calculate_partition_entry_array_crc32(merged_entries_raw)
    merged_h.header_crc32 = merged_h.calculate_header_crc32()

    # Should be valid
    assert merged_h.is_valid()

    # Encode header
    merged_h_raw = gpt.encode_gpt_header(merged_h)

    m_start, m_end = entries_range(merged_h)
    assert m_end - m_start == len(merged_entries_raw)

    # Construct the new partition table
    merged_raw = bytearray(0x400)
    merged_raw[:0x200] = sample1[:0x200]    # Copy protective MBR from disk1
    merged_raw[0x200:0x200+merged_h.header_size] = merged_h_raw
    merged_raw[m_start:m_end] = merged_entries_raw

    # Did we get what we expect?
    assert merged_raw == sample_merged
