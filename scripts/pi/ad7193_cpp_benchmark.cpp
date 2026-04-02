/**
 * AD7193 (Pmod AD5) driver + I/Q pair-rate benchmark for Raspberry Pi (spidev).
 *
 * Mirrors register protocol and read_iq_stream() behavior in hardware/ad7193.py
 * so results are comparable to:
 *   python scripts/pi/live_adc_view.py --mode max-rate --acq-mode stream \\
 *     --benchmark-raw --no-plot --duration SEC --spi-speed HZ --result-json
 *
 * Build on the Pi:
 *   sudo apt install g++
 *   cd scripts/pi
 *   g++ -O3 -std=c++17 ad7193_cpp_benchmark.cpp -o ad7193_cpp_benchmark
 *   (-O3 is capital letter O + 3, not -03 with a zero)
 *
 * Run:
 *   ./ad7193_cpp_benchmark --seconds 30 --spi-speed 2000000
 *   ./ad7193_cpp_benchmark --seconds 30 --json-result
 *
 * Compare with Python (same Pi, same wiring):
 *   cd ~/SPAM && source venv/bin/activate
 *   python scripts/pi/live_adc_view.py --mode max-rate --acq-mode stream \\
 *     --benchmark-raw --no-plot --duration 30 --spi-speed 2000000 --result-json
 */

#include <linux/spi/spidev.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <chrono>
#include <algorithm>
#include <optional>
#include <string>

constexpr uint8_t kRegStatus = 0x00;
constexpr uint8_t kRegMode = 0x01;
constexpr uint8_t kRegConfig = 0x02;
constexpr uint8_t kRegData = 0x03;
constexpr uint8_t kRegId = 0x04;

constexpr uint8_t kCommWrite = 0x00;
constexpr uint8_t kCommRead = 0x40;

constexpr uint32_t kModeSingle = 0x200000;
constexpr uint32_t kModeIdle = 0x400000;
constexpr uint32_t kModeCont = 0x000000;
constexpr uint32_t kModeClkInt = 0x080000;
constexpr uint32_t kModeDatSta = 0x100000;

constexpr uint32_t kConfigRefsel = 0x000000;
constexpr uint32_t kConfigBuf = 0x000010;

constexpr uint32_t kDiffCh0 = 0x0100;
constexpr uint32_t kDiffCh1 = 0x0200;

constexpr double kVref = 2.5;
constexpr double kMclkHz = 4'915'200.0;

constexpr uint32_t kAd7193MaxSpiHz = 6'170'000;

inline uint8_t write_cmd(uint8_t reg) {
    return static_cast<uint8_t>(kCommWrite | (reg << 3));
}
inline uint8_t read_cmd(uint8_t reg) {
    return static_cast<uint8_t>(kCommRead | (reg << 3));
}

int gain_bits(int gain) {
    switch (gain) {
        case 1: return 0;
        case 8: return 3;
        case 16: return 4;
        case 32: return 5;
        case 64: return 6;
        case 128: return 7;
        default: return 0;
    }
}

bool set_spi_mode(int fd, uint32_t mode) {
    if (ioctl(fd, SPI_IOC_WR_MODE32, &mode) == 0)
        return true;
    uint8_t m = static_cast<uint8_t>(mode & 0xFFU);
    return ioctl(fd, SPI_IOC_WR_MODE, &m) == 0;
}

bool set_bits(int fd, uint8_t bits) {
    return ioctl(fd, SPI_IOC_WR_BITS_PER_WORD, &bits) == 0;
}

bool spi_xfer(int fd, uint32_t speed_hz, const uint8_t* tx, uint8_t* rx, size_t len) {
    uint32_t max_hz = speed_hz;
    (void)ioctl(fd, SPI_IOC_WR_MAX_SPEED_HZ, &max_hz);
    struct spi_ioc_transfer tr;
    std::memset(&tr, 0, sizeof(tr));
    tr.tx_buf = static_cast<unsigned long long>(reinterpret_cast<uintptr_t>(tx));
    tr.rx_buf = static_cast<unsigned long long>(reinterpret_cast<uintptr_t>(rx));
    tr.len = static_cast<uint32_t>(len);
    tr.speed_hz = speed_hz;
    tr.bits_per_word = 8;
    /* POSIX: ioctl success is nonnegative; some kernels return >0, not only 0. */
    return ioctl(fd, SPI_IOC_MESSAGE(1), &tr) >= 0;
}

using Clock = std::chrono::steady_clock;

inline double seconds_since(Clock::time_point t0) {
    return std::chrono::duration<double>(Clock::now() - t0).count();
}

/** Add floating-point seconds to a time_point (portable with integral steady_clock::duration). */
inline Clock::time_point add_duration_sec(Clock::time_point t, double sec) {
    return t + std::chrono::duration_cast<Clock::duration>(
               std::chrono::duration<double>(sec));
}

class AD7193 {
public:
    AD7193(const char* device, uint32_t speed_hz) : speed_hz_(speed_hz) {
        fd_ = open(device, O_RDWR);
        if (fd_ < 0) {
            std::fprintf(stderr, "open %s: %s\n", device, strerror(errno));
            std::exit(1);
        }
        const uint32_t mode3 = SPI_MODE_3;
        if (!set_spi_mode(fd_, mode3)) {
            std::perror("SPI_IOC_WR_MODE32/MODE");
            std::exit(1);
        }
        uint8_t bits = 8;
        if (!set_bits(fd_, bits)) {
            std::perror("SPI_IOC_WR_BITS_PER_WORD");
            std::exit(1);
        }
        reset();
        verify_id();
    }

    ~AD7193() {
        if (fd_ >= 0) {
            stop_stream();
            close(fd_);
        }
    }

    AD7193(const AD7193&) = delete;
    AD7193& operator=(const AD7193&) = delete;

    void configure(int gain, int data_rate_hz) {
        gain_ = gain;
        fs_val_ = fs_from_data_rate(data_rate_hz);
        mode_single_val_ = kModeSingle | kModeClkInt | (fs_val_ & 0x3FFU);
        const uint32_t gb = static_cast<uint32_t>(gain_bits(gain));
        base_config_ = kConfigRefsel | kConfigBuf | gb;
        streaming_ = false;

        write_reg(kRegMode, mode_single_val_, 3);
        write_reg(kRegConfig, base_config_, 3);

        const double realized = (kMclkHz / 1024.0) / static_cast<double>(fs_val_);
        std::printf("[INFO] AD7193 config: gain=%d FS=%u data_rate_req=%dHz realized~%.1fHz\n",
                    gain_, fs_val_, data_rate_hz, realized);
    }

    void start_iq_stream() {
        const uint32_t stream_cfg = base_config_ | kDiffCh0 | kDiffCh1;
        const uint32_t stream_mode =
            kModeCont | kModeClkInt | kModeDatSta | (fs_val_ & 0x3FFU);
        if (!write_reg(kRegConfig, stream_cfg, 3) || !write_reg(kRegMode, stream_mode, 3)) {
            std::fprintf(stderr, "[ERROR] start_iq_stream: SPI write failed (%s)\n", strerror(errno));
        }
        streaming_ = true;
        last_stream_chd_ = -1;
    }

    void stop_stream() {
        if (fd_ < 0 || !streaming_)
            return;
        const uint32_t idle = kModeIdle | kModeClkInt | (fs_val_ & 0x3FFU);
        write_reg(kRegMode, idle, 3);
        streaming_ = false;
    }

    /** One full I+Q pair (same semantics as Python read_iq_stream). */
    void read_iq_stream(double timeout_s, bool fast_path, double* i_out, double* q_out) {
        if (!streaming_)
            start_iq_stream();

        std::optional<double> i_v;
        std::optional<double> q_v;
        const Clock::time_point t0 = Clock::now();
        const double tmo = std::max(0.01, timeout_s);
        const Clock::time_point t_deadline = add_duration_sec(t0, tmo);
        const double fast_frac = fast_path ? 0.6 : 1.0;
        const Clock::time_point t_fast_end = add_duration_sec(t0, fast_frac * tmo);

        /* Stage 1: fast path (matches hardware/ad7193.py) */
        while (fast_path && Clock::now() < t_fast_end && (!i_v.has_value() || !q_v.has_value())) {
            uint32_t st = 0;
            if (!read_reg(kRegStatus, 1, st))
                continue;
            if (st & 0x80U)
                continue;
            uint32_t d32 = 0;
            if (!read_reg(kRegData, 4, d32))
                continue;
            const uint32_t raw = (d32 >> 8) & 0xFFFFFFU;
            const int chd = static_cast<int>(d32 & 0x0FU);
            if (chd == last_stream_chd_)
                continue;
            last_stream_chd_ = chd;
            if (chd == 0)
                i_v = raw_to_voltage(raw);
            else if (chd == 1)
                q_v = raw_to_voltage(raw);
        }

        /* Stage 2: conservative fallback */
        while (Clock::now() < t_deadline && (!i_v.has_value() || !q_v.has_value())) {
            const double rem =
                std::chrono::duration<double>(t_deadline - Clock::now()).count();
            if (rem < 0.001)
                break;
            if (!wait_ready(std::min(0.05, rem), 0.00002))
                continue;
            uint32_t d32 = 0;
            if (!read_reg(kRegData, 4, d32))
                continue;
            const uint32_t raw = (d32 >> 8) & 0xFFFFFFU;
            const int chd = static_cast<int>(d32 & 0x0FU);
            last_stream_chd_ = chd;
            if (chd == 0)
                i_v = raw_to_voltage(raw);
            else if (chd == 1)
                q_v = raw_to_voltage(raw);
        }

        if (!i_v.has_value() || !q_v.has_value()) {
            ++stream_timeout_count_;
            if ((stream_timeout_count_ % 25U) == 1U) {
                std::fprintf(stderr,
                             "[WARN] AD7193: stream timeout waiting for I/Q (using last valid sample)\n");
            }
            if (!i_v.has_value())
                i_v = last_i_;
            if (!q_v.has_value())
                q_v = last_q_;
        } else {
            last_i_ = *i_v;
            last_q_ = *q_v;
        }

        *i_out = *i_v;
        *q_out = *q_v;
    }

    uint64_t stream_timeout_count() const { return stream_timeout_count_; }

private:
    static uint32_t fs_from_data_rate(int data_rate_hz) {
        const double rate = std::max(0.1, static_cast<double>(data_rate_hz));
        int fs = static_cast<int>((kMclkHz / 1024.0) / rate);
        if (fs < 1) fs = 1;
        if (fs > 1023) fs = 1023;
        return static_cast<uint32_t>(fs);
    }

    double raw_to_voltage(uint32_t raw24) const {
        /* Match hardware/ad7193.py _raw_to_voltage (unsigned 24-bit code) */
        const double raw = static_cast<double>(raw24 & 0xFFFFFFU);
        return (raw / 8388608.0 - 1.0) * kVref / static_cast<double>(gain_);
    }

    void reset() {
        static const uint8_t kReset[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
        uint8_t rx[6]{};
        if (!spi_xfer(fd_, speed_hz_, kReset, rx, sizeof(kReset))) {
            std::fprintf(stderr, "[WARN] reset xfer failed: %s\n", strerror(errno));
        }
        usleep(10000);
    }

    void verify_id() {
        uint32_t id_val = 0;
        if (!read_reg(kRegId, 1, id_val)) {
            std::fprintf(stderr, "[WARN] ID read failed\n");
            return;
        }
        if ((id_val & 0x0FU) != 0x02U)
            std::fprintf(stderr, "[WARN] AD7193: unexpected ID=0x%02X (expected 0xX2)\n",
                         static_cast<unsigned>(id_val & 0xFFU));
        else
            std::printf("[INFO] AD7193: ID=0x%02X verified\n", static_cast<unsigned>(id_val & 0xFFU));
    }

    bool write_reg(uint8_t reg, uint32_t value, int nbytes) {
        uint8_t tx[4]{};
        tx[0] = write_cmd(reg);
        for (int i = nbytes - 1, j = 1; i >= 0; --i, ++j)
            tx[j] = static_cast<uint8_t>((value >> (8 * i)) & 0xFFU);
        uint8_t rx[4]{};
        return spi_xfer(fd_, speed_hz_, tx, rx, static_cast<size_t>(1 + nbytes));
    }

    bool read_reg(uint8_t reg, int nbytes, uint32_t& value_out) {
        if (nbytes > 4)
            return false;
        uint8_t tx[8]{};
        uint8_t rx[8]{};
        tx[0] = read_cmd(reg);
        for (int i = 1; i <= nbytes; ++i)
            tx[i] = 0;
        if (!spi_xfer(fd_, speed_hz_, tx, rx, static_cast<size_t>(1 + nbytes)))
            return false;
        value_out = 0;
        for (int i = 1; i <= nbytes; ++i)
            value_out = (value_out << 8) | rx[i];
        return true;
    }

    bool wait_ready(double timeout_s, double poll_sleep_s) {
        const Clock::time_point deadline =
            add_duration_sec(Clock::now(), timeout_s);
        while (Clock::now() < deadline) {
            uint32_t status = 0;
            if (!read_reg(kRegStatus, 1, status))
                return false;
            if ((status & 0x80U) == 0)
                return true;
            if (poll_sleep_s > 0)
                usleep(static_cast<useconds_t>(poll_sleep_s * 1e6));
        }
        return false;
    }

    int fd_ = -1;
    uint32_t speed_hz_;
    int gain_ = 1;
    uint32_t fs_val_ = 1;
    uint32_t mode_single_val_ = 0;
    uint32_t base_config_ = 0;
    bool streaming_ = false;
    int last_stream_chd_ = -1;
    double last_i_ = 0.0;
    double last_q_ = 0.0;
    uint64_t stream_timeout_count_ = 0;
};

struct Args {
    const char* device = "/dev/spidev0.0";
    uint32_t spi_speed = 1'000'000;
    int gain = 1;
    int data_rate = 96;
    double seconds = 10.0;
    bool fast_path = true;
    bool json_result = false;
    bool quiet = false;
};

void print_usage() {
    std::fprintf(stderr,
        "Usage: ad7193_cpp_benchmark [options]\n"
        "  --device PATH      spidev (default /dev/spidev0.0)\n"
        "  --spi-speed HZ     SPI clock (default 1000000, max ~6170000 for AD7193)\n"
        "  --gain N           1,8,16,32,64,128 (default 1)\n"
        "  --data-rate HZ     requested output rate (default 96)\n"
        "  --seconds SEC      benchmark duration (default 10)\n"
        "  --fast-path        use two-stage read (default on)\n"
        "  --no-fast-path     conservative stream read only\n"
        "  --json-result      print grep-friendly RESULT line\n"
        "  --quiet            less console output\n"
        "  -h, --help\n");
}

bool parse_args(int argc, char** argv, Args& a) {
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "-h") == 0 || std::strcmp(argv[i], "--help") == 0) {
            print_usage();
            return false;
        }
        auto need = [&](const char* name) -> const char* {
            if (i + 1 >= argc) {
                std::fprintf(stderr, "Missing value for %s\n", name);
                return nullptr;
            }
            return argv[++i];
        };
        if (std::strcmp(argv[i], "--device") == 0) {
            const char* v = need("--device");
            if (!v) return false;
            a.device = v;
        } else if (std::strcmp(argv[i], "--spi-speed") == 0) {
            const char* v = need("--spi-speed");
            if (!v) return false;
            a.spi_speed = static_cast<uint32_t>(std::strtoul(v, nullptr, 10));
        } else if (std::strcmp(argv[i], "--gain") == 0) {
            const char* v = need("--gain");
            if (!v) return false;
            a.gain = static_cast<int>(std::strtol(v, nullptr, 10));
        } else if (std::strcmp(argv[i], "--data-rate") == 0) {
            const char* v = need("--data-rate");
            if (!v) return false;
            a.data_rate = static_cast<int>(std::strtol(v, nullptr, 10));
        } else if (std::strcmp(argv[i], "--seconds") == 0) {
            const char* v = need("--seconds");
            if (!v) return false;
            a.seconds = std::strtod(v, nullptr);
        } else if (std::strcmp(argv[i], "--fast-path") == 0) {
            a.fast_path = true;
        } else if (std::strcmp(argv[i], "--no-fast-path") == 0) {
            a.fast_path = false;
        } else if (std::strcmp(argv[i], "--json-result") == 0) {
            a.json_result = true;
        } else if (std::strcmp(argv[i], "--quiet") == 0) {
            a.quiet = true;
        } else {
            std::fprintf(stderr, "Unknown option: %s\n", argv[i]);
            return false;
        }
    }
    return true;
}

int main(int argc, char** argv) {
    Args args;
    if (!parse_args(argc, argv, args))
        return argc > 1 ? 1 : 0;

    if (args.spi_speed > kAd7193MaxSpiHz) {
        std::fprintf(stderr, "[WARN] clamping SPI speed %u to %u Hz (AD7193 max)\n",
                     args.spi_speed, kAd7193MaxSpiHz);
        args.spi_speed = kAd7193MaxSpiHz;
    }
    if (args.seconds <= 0) {
        std::fprintf(stderr, "seconds must be > 0\n");
        return 1;
    }

    if (!args.quiet) {
        std::printf("[INFO] device=%s spi_speed=%u gain=%d data_rate=%d fast_path=%d\n",
                    args.device, args.spi_speed, args.gain, args.data_rate,
                    args.fast_path ? 1 : 0);
    }

    AD7193 adc(args.device, args.spi_speed);
    adc.configure(args.gain, args.data_rate);
    adc.start_iq_stream();

    double i_v = 0, q_v = 0;
    uint64_t pairs = 0;
    const Clock::time_point t0 = Clock::now();
    while (seconds_since(t0) < args.seconds) {
        adc.read_iq_stream(0.5, args.fast_path, &i_v, &q_v);
        ++pairs;
    }
    const double elapsed = seconds_since(t0);
    adc.stop_stream();

    const double pair_hz = (elapsed > 0.0) ? (static_cast<double>(pairs) / elapsed) : 0.0;
    const uint64_t timeouts = adc.stream_timeout_count();

    if (!args.quiet) {
        std::printf("\n=== Summary ===\n");
        std::printf("pairs=%llu elapsed=%.3fs pair_hz=%.4f stream_timeouts=%llu\n",
                    static_cast<unsigned long long>(pairs),
                    elapsed,
                    pair_hz,
                    static_cast<unsigned long long>(timeouts));
        std::printf("last_sample I=%.6f V Q=%.6f V\n", i_v, q_v);
    }

    if (args.json_result) {
        std::printf(
            "RESULT pairs=%llu elapsed_s=%.4f pair_hz=%.4f stream_timeouts=%llu "
            "spi_speed=%u gain=%d data_rate=%d fast_path=%d\n",
            static_cast<unsigned long long>(pairs),
            elapsed,
            pair_hz,
            static_cast<unsigned long long>(timeouts),
            args.spi_speed,
            args.gain,
            args.data_rate,
            args.fast_path ? 1 : 0);
    }

    return 0;
}
