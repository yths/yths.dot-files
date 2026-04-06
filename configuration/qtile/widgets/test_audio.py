import numpy
import sounddevice
import time

def compress_array(arr, m):
    n = len(arr)
    if m > n:
        raise ValueError("m must be less than or equal to n")
    # Calculate the size of each bin
    bins = numpy.linspace(0, n, m+1, dtype=int)
    compressed = numpy.array([arr[bins[i]:bins[i+1]].sum() for i in range(m)])
    return compressed

def calculate_spectrum(indata, frames, time, status):
    if status:
        print(status)
    fft_data = numpy.abs(numpy.fft.fft(indata - numpy.mean(indata, axis=0), axis=0))
    #freqs = numpy.fft.fftfreq(len(fft_data), 1/44100)
    spectrum = fft_data[:len(fft_data)//2, :]
    spectrum_left = spectrum[:, 0]
    spectrum_right = spectrum[:, 1]
    #print("Frequencies:", freqs[:len(fft_data)//2])
    #print("Spectrum:", spectrum)
    try:
        compressed_spectrum_left = compress_array(spectrum_left, 8)
        compressed_spectrum_right = compress_array(spectrum_right, 8)
        compressed_spectrum = numpy.concatenate((compressed_spectrum_left[::-1], compressed_spectrum_right))
        compressed_spectrum /= numpy.max([numpy.max(compressed_spectrum), 2])
        discretized_spectrum = numpy.round(compressed_spectrum * 8).astype(int)
        if numpy.sum(discretized_spectrum) > 0:
            unicode_blocks = [chr(0x2581 + h) if h > 0 else ' ' for h in discretized_spectrum]
            print(f"\rCompressed Spectrum: {''.join(unicode_blocks)} {numpy.sum(compressed_spectrum)}", end='', flush=True)
    except ValueError as e:
        pass
        #print("Error in compressing spectrum:", e)

if __name__ == '__main__':
    print("Starting audio stream...")

    sounddevice.default.device = 31
    device_properties = sounddevice.query_devices(sounddevice.default.device)
    print("Using device:", device_properties['name'])
    print(device_properties)
    with sounddevice.InputStream(channels=2, samplerate=device_properties['default_samplerate'], callback=calculate_spectrum) as stream:
        print(stream)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopped by user")