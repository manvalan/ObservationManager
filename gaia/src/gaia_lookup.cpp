#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <vector>
#include <cstdlib>
#include <nlohmann/json.hpp>
#include <ioc_gaialib/unified_gaia_catalog.h>

using json = nlohmann::json;

static std::string readEnvOrDefault(const char* key, const std::string& def) {
    const char* v = std::getenv(key);
    return v ? std::string(v) : def;
}

static std::string defaultConfigJSON() {
    std::string home = readEnvOrDefault("HOME", "");
    std::string dir = home + "/.catalog/gaia_mag18_v2_multifile";
    json cfg = {
        {"catalog_type", "multifile_v2"},
        {"multifile_directory", dir}
    };
    return cfg.dump();
}

static void ensureInit(const std::optional<std::string>& cfg) {
    static bool inited = false;
    if (!inited) {
        std::string conf = cfg ? *cfg : defaultConfigJSON();
        if (!ioc::gaia::UnifiedGaiaCatalog::initialize(conf)) {
            std::cerr << "Failed to initialize IOC_GaiaLib with provided config" << std::endl;
            std::exit(2);
        }
        inited = true;
    }
}

static int cmdByName(const std::string& name, const std::optional<std::string>& cfg) {
    ensureInit(cfg);
    auto& cat = ioc::gaia::UnifiedGaiaCatalog::getInstance();
    auto res = cat.queryByName(name);
    json out;
    if (res) {
        out = {
            {"ok", true},
            {"name", name},
            {"source_id", res->source_id},
            {"ra_deg", res->ra},
            {"dec_deg", res->dec},
            {"mag_g", res->phot_g_mean_mag},
            {"designations", res->getAllDesignations()}
        };
    } else {
        out = {{"ok", false}};
    }
    std::cout << out.dump() << std::endl;
    return res ? 0 : 1;
}

static int cmdCone(double ra, double dec, double radius, double maxmag, const std::optional<std::string>& cfg) {
    ensureInit(cfg);
    auto& cat = ioc::gaia::UnifiedGaiaCatalog::getInstance();
    ioc::gaia::QueryParams p;
    p.ra_center = ra;
    p.dec_center = dec;
    p.radius = radius;
    p.max_magnitude = maxmag;
    auto stars = cat.queryCone(p);
    json arr = json::array();
    for (const auto& s : stars) {
        arr.push_back({
            {"source_id", s.source_id},
            {"ra_deg", s.ra},
            {"dec_deg", s.dec},
            {"mag_g", s.phot_g_mean_mag},
            {"designation", s.getDesignation()}
        });
    }
    std::cout << arr.dump() << std::endl;
    return 0;
}

int main(int argc, char** argv) {
    // Simple CLI:
    // gaia_lookup --name "Vega" [--config-json '{...}']
    // gaia_lookup --sao 151881 | --hip 32349 | --hd 48915
    // gaia_lookup --cone RA DEC RADIUS [--maxmag 12] [--config-json '{...}']
    std::optional<std::string> cfg;
    std::string mode;
    std::string name;
    std::string sao, hip, hd;
    double ra = 0, dec = 0, radius = 1.0, maxmag = 20.0;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--name" && i + 1 < argc) { mode = "name"; name = argv[++i]; }
        else if (a == "--cone" && i + 3 < argc) { mode = "cone"; ra = std::stod(argv[++i]); dec = std::stod(argv[++i]); radius = std::stod(argv[++i]); }
        else if (a == "--sao" && i + 1 < argc) { mode = "sao"; sao = argv[++i]; }
        else if (a == "--hip" && i + 1 < argc) { mode = "hip"; hip = argv[++i]; }
        else if (a == "--hd" && i + 1 < argc) { mode = "hd"; hd = argv[++i]; }
        else if (a == "--maxmag" && i + 1 < argc) { maxmag = std::stod(argv[++i]); }
        else if (a == "--config-json" && i + 1 < argc) { cfg = std::string(argv[++i]); }
        else if (a == "-h" || a == "--help") {
            std::cout << "Usage:\n"
                         "  gaia_lookup --name <NAME> [--config-json '<json>']\n"
                         "  gaia_lookup --sao <NUM> | --hip <NUM> | --hd <NUM> [--config-json '<json>']\n"
                         "  gaia_lookup --cone <RA> <DEC> <RADIUS> [--maxmag <G>] [--config-json '<json>']\n";
            return 0;
        }
    }

    if (mode == "name" && !name.empty()) {
        return cmdByName(name, cfg);
    } else if (mode == "sao" && !sao.empty()) {
        ensureInit(cfg);
        auto& cat = ioc::gaia::UnifiedGaiaCatalog::getInstance();
        auto res = cat.queryBySAO(sao);
        json out = res ? json{{"ok", true}, {"name", "SAO " + sao}, {"source_id", res->source_id}, {"ra_deg", res->ra}, {"dec_deg", res->dec}, {"mag_g", res->phot_g_mean_mag}, {"designations", res->getAllDesignations()}} : json{{"ok", false}};
        std::cout << out.dump() << std::endl;
        return res ? 0 : 1;
    } else if (mode == "hip" && !hip.empty()) {
        ensureInit(cfg);
        auto& cat = ioc::gaia::UnifiedGaiaCatalog::getInstance();
        auto res = cat.queryByHipparcos(hip);
        json out = res ? json{{"ok", true}, {"name", "HIP " + hip}, {"source_id", res->source_id}, {"ra_deg", res->ra}, {"dec_deg", res->dec}, {"mag_g", res->phot_g_mean_mag}, {"designations", res->getAllDesignations()}} : json{{"ok", false}};
        std::cout << out.dump() << std::endl;
        return res ? 0 : 1;
    } else if (mode == "hd" && !hd.empty()) {
        ensureInit(cfg);
        auto& cat = ioc::gaia::UnifiedGaiaCatalog::getInstance();
        auto res = cat.queryByHD(hd);
        json out = res ? json{{"ok", true}, {"name", "HD " + hd}, {"source_id", res->source_id}, {"ra_deg", res->ra}, {"dec_deg", res->dec}, {"mag_g", res->phot_g_mean_mag}, {"designations", res->getAllDesignations()}} : json{{"ok", false}};
        std::cout << out.dump() << std::endl;
        return res ? 0 : 1;
    } else if (mode == "cone") {
        return cmdCone(ra, dec, radius, maxmag, cfg);
    }
    std::cerr << "Missing or invalid arguments. Use --help." << std::endl;
    return 1;
}
