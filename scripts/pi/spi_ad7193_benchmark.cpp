/**
 * AD7193-shaped SPI throughput benchmark (Raspberry Pi / Linux spidev).
 *
 * Measures how many SPI transactions per second you can sustain at different
 * SPI clock rates. This isolates the SPI stack from Python — it does not
 * guarantee valid ADC conversions unless the part is already configured.
 *
 * Build on the Pi:
 *   sudo apt install g++
 *   cd scripts/pi
 *   g++ -O3 -std=c++17 spi_ad7193_benchmark.cpp -o spi_ad7193_benchmark
 *   (-O3 is capital letter O + 3, not -03 with a zero)
 *
 * Run:
 *   ./spi_ad7193_benchmark --device /dev/spidev0.0 --seconds 2
 *   ./spi_ad7193_benchmark --mode status-data --speeds 500000,1000000,2000000,4000000
 */

#include <linux/spi/spidev.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <chrono>
#include <string>
#include <vector>

namespace {

constexpr uint8_t kCommRead = 0x40;
constexpr uint8_t kRegStatus = 0x00;
constexpr uint8_t kRegData = 0x03;

inline uint8_t read_cmd(uint8_t reg) {
    return static_cast<uint8_t>(kCommRead | (reg << 3));
}

bool set_spi_mode(int fd, uint32_t mode) {
    if (ioctl(fd, SPI_IOC_WR_MODE32, &mode) == 0)
        return true;
    /* Older kernels / headers: 8-bit mode word */
    uint8_t m = static_cast<uint8_t>(mode & 0xFFU);
    return ioctl(fd, SPI_IOC_WR_MODE, &m) == 0;
}

bool set_bits(int fd, uint8_t bits) {
    return ioctl(fd, SPI_IOC_WR_BITS_PER_WORD, &bits) == 0;
}

bool xfer(int fd, uint32_t speed_hz, const uint8_t* tx, uint8_t* rx, size_t len) {
    /*
     * Raspberry Pi spidev: set device max speed before SPI_IOC_MESSAGE.
     * Zero the whole spi_ioc_transfer so newer kernel padding fields are 0.
     * Use 64-bit buffer fields (__u64) via uintptr_t cast.
     */
    uint32_t max_hz = speed_hz;
    /* Optional on some kernels; transfer still carries speed_hz. */
    (void)ioctl(fd, SPI_IOC_WR_MAX_SPEED_HZ, &max_hz);

    struct spi_ioc_transfer tr;
    std::memset(&tr, 0, sizeof(tr));
    tr.tx_buf = static_cast<unsigned long long>(reinterpret_cast<uintptr_t>(tx));
    tr.rx_buf = static_cast<unsigned long long>(reinterpret_cast<uintptr_t>(rx));
    tr.len = static_cast<uint32_t>(len);
    tr.speed_hz = speed_hz;
    tr.bits_per_word = 8;

    if (ioctl(fd, SPI_IOC_MESSAGE(1), &tr) < 0)
        return false;
    return true;
}

bool reset_ad7193(int fd, uint32_t speed_hz) {
    static const uint8_t kReset[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
    uint8_t rx[6]{};
    if (!xfer(fd, speed_hz, kReset, rx, sizeof(kReset))) {
        std::fprintf(stderr, "Reset SPI xfer failed: %s\n", strerror(errno));
        return false;
    }
    usleep(10000);
    return true;
}

void print_usage() {
    std::fprintf(stderr,
        "Usage: spi_ad7193_benchmark [options]\n"
        "  --device PATH     spidev path (default /dev/spidev0.0)\n"
        "  --seconds SEC     run duration per speed test (default 2.0)\n"
        "  --warmup SEC      warmup before each timed block (default 0.05)\n"
        "  --speeds LIST     comma-separated Hz, e.g. 500000,1000000,2000000\n"
        "                    default: 100000,500000,1000000,2000000,4000000,5000000\n"
        "  --mode MODE       data-only | status-data (default data-only)\n"
        "      data-only     one READ DATA 4-byte (+status) = 5-byte SPI frame\n"
        "      status-data   READ STATUS (1B) then READ DATA (4B) like conservative poll\n"
        "  --no-reset        skip 0xFF reset burst at start\n"
        "\n"
        "Output: RESULT lines are easy to grep for spreadsheets.\n");
}

std::vector<uint32_t> parse_speeds(const char* s) {
    std::vector<uint32_t> out;
    std::string cur;
    auto flush = [&]() {
        if (cur.empty()) return;
        char* end = nullptr;
        unsigned long v = std::strtoul(cur.c_str(), &end, 10);
        if (end != cur.c_str() && v > 0 && v <= 20000000UL)
            out.push_back(static_cast<uint32_t>(v));
        cur.clear();
    };
    for (const char* p = s; *p; ++p) {
        if (*p == ',' || *p == ' ')
            flush();
        else
            cur.push_back(*p);
    }
    flush();
    return out;
}

enum class Mode { DataOnly, StatusThenData };

struct Args {
    const char* device = "/dev/spidev0.0";
    double seconds = 2.0;
    double warmup = 0.05;
    Mode mode = Mode::DataOnly;
    bool do_reset = true;
    std::vector<uint32_t> speeds = {100000, 500000, 1000000, 2000000, 4000000, 5000000};
};

bool parse_args(int argc, char** argv, Args& a) {
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--help") == 0 || std::strcmp(argv[i], "-h") == 0) {
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
        } else if (std::strcmp(argv[i], "--seconds") == 0) {
            const char* v = need("--seconds");
            if (!v) return false;
            a.seconds = std::strtod(v, nullptr);
        } else if (std::strcmp(argv[i], "--warmup") == 0) {
            const char* v = need("--warmup");
            if (!v) return false;
            a.warmup = std::strtod(v, nullptr);
        } else if (std::strcmp(argv[i], "--speeds") == 0) {
            const char* v = need("--speeds");
            if (!v) return false;
            auto sp = parse_speeds(v);
            if (sp.empty()) {
                std::fprintf(stderr, "No valid speeds in --speeds\n");
                return false;
            }
            a.speeds = std::move(sp);
        } else if (std::strcmp(argv[i], "--mode") == 0) {
            const char* v = need("--mode");
            if (!v) return false;
            if (std::strcmp(v, "data-only") == 0)
                a.mode = Mode::DataOnly;
            else if (std::strcmp(v, "status-data") == 0)
                a.mode = Mode::StatusThenData;
            else {
                std::fprintf(stderr, "Unknown mode %s\n", v);
                return false;
            }
        } else if (std::strcmp(argv[i], "--no-reset") == 0) {
            a.do_reset = false;
        } else {
            std::fprintf(stderr, "Unknown arg: %s\n", argv[i]);
            return false;
        }
    }
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    Args args;
    if (!parse_args(argc, argv, args))
        return args.speeds.empty() ? 0 : 1;

    int fd = open(args.device, O_RDWR);
    if (fd < 0) {
        std::perror("open");
        return 1;
    }

    const uint32_t mode3 = SPI_MODE_3;
    if (!set_spi_mode(fd, mode3)) {
        std::perror("SPI_IOC_WR_MODE32");
        close(fd);
        return 1;
    }
    uint8_t bits = 8;
    if (!set_bits(fd, bits)) {
        std::perror("SPI_IOC_WR_BITS_PER_WORD");
        close(fd);
        return 1;
    }

    const uint32_t first_speed = args.speeds.empty() ? 100000u : args.speeds[0];
    if (args.do_reset && !reset_ad7193(fd, first_speed)) {
        std::fprintf(stderr, "Reset skipped or failed (continuing without reset)\n");
    }

    // Buffers: AD7193 read DATA with DAT_STA appends status in LSB of 32-bit read = 4 response bytes after cmd.
    uint8_t tx_data[5]{read_cmd(kRegData), 0, 0, 0, 0};
    uint8_t rx_data[5]{};
    uint8_t tx_stat[2]{read_cmd(kRegStatus), 0};
    uint8_t rx_stat[2]{};

    const char* mode_str = (args.mode == Mode::DataOnly) ? "data-only" : "status-data";

    std::printf("# spi_ad7193_benchmark device=%s mode=%s duration_per_speed=%.3fs\n",
                args.device, mode_str, args.seconds);
    std::printf("# RESULT speed_hz xfer_per_sec bytes_per_xfer note\n");

    for (uint32_t hz : args.speeds) {
        // Warmup: prime caches / governor
        const auto w0 = std::chrono::steady_clock::now();
        uint64_t wcount = 0;
        while (true) {
            const auto w1 = std::chrono::steady_clock::now();
            std::chrono::duration<double> wd = w1 - w0;
            if (wd.count() >= args.warmup)
                break;
            if (args.mode == Mode::DataOnly) {
                if (!xfer(fd, hz, tx_data, rx_data, sizeof(tx_data)))
                    break;
            } else {
                if (!xfer(fd, hz, tx_stat, rx_stat, sizeof(tx_stat)))
                    break;
                if (!xfer(fd, hz, tx_data, rx_data, sizeof(tx_data)))
                    break;
            }
            ++wcount;
        }

        uint64_t count = 0;
        const auto t0 = std::chrono::steady_clock::now();
        while (true) {
            const auto t1 = std::chrono::steady_clock::now();
            std::chrono::duration<double> elapsed = t1 - t0;
            if (elapsed.count() >= args.seconds)
                break;

            if (args.mode == Mode::DataOnly) {
                if (!xfer(fd, hz, tx_data, rx_data, sizeof(tx_data))) {
                    std::fprintf(stderr, "SPI xfer failed at %u Hz: %s\n", hz, strerror(errno));
                    close(fd);
                    return 1;
                }
            } else {
                if (!xfer(fd, hz, tx_stat, rx_stat, sizeof(tx_stat))) {
                    std::fprintf(stderr, "SPI status xfer failed at %u Hz: %s\n", hz, strerror(errno));
                    close(fd);
                    return 1;
                }
                if (!xfer(fd, hz, tx_data, rx_data, sizeof(tx_data))) {
                    std::fprintf(stderr, "SPI data xfer failed at %u Hz: %s\n", hz, strerror(errno));
                    close(fd);
                    return 1;
                }
            }
            ++count;
        }

        const auto t_end = std::chrono::steady_clock::now();
        const double dt = std::chrono::duration<double>(t_end - t0).count();
        const double xps = (dt > 0.0) ? (static_cast<double>(count) / dt) : 0.0;
        const unsigned bpx = (args.mode == Mode::DataOnly) ? 5u : (2u + 5u);

        std::printf("RESULT %u %.2f %u ad7193-shaped-%s\n", hz, xps, bpx, mode_str);
        std::printf("  -> %.0f Hz SPI clock: %.0f xfers/s (outer loop); ~%.0f bytes/s on wire\n",
                    static_cast<double>(hz), xps, xps * static_cast<double>(bpx));
    }

    close(fd);
    return 0;
}
