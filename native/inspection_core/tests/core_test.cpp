#include "inspection.hpp"
#include <iostream>
#include <stdexcept>
void check(bool value) { if (!value) throw std::runtime_error("Native expectation failed"); }
int main() {
  try {
    auto foreign = vision::inspect({"foreign", "full", 90, 20});
    check(foreign.at("regions").size() == 2);
    check(foreign.at("regions")[0].at("area") == 80);
    check(foreign.at("regions")[1].at("area") == 36);
    check(vision::inspect({"foreign", "full", 45, 20}).at("missedPixels") == 116);
    check(vision::inspect({"foreign", "full", 46, 80}).at("regions").size() == 1);
    check(vision::inspect({"foreign", "center", 90, 20}).at("excludedPixels") == 36);
    check(vision::inspect({"lighting", "full", 130, 20}).at("falsePixels") == 4000);
    check(vision::inspect({"normal", "full", 90, 1}).at("falsePixels") == 4);
    check(vision::inspect({"normal", "full", 255, 16000}).at("regions")[0].at("area") == 16000);
    check(vision::inspect({"normal", "full", 0, 1}).at("status") == "OK");
    bool rejected = false;
    try { vision::inspect({"unknown", "full", 90, 20}); } catch (const std::invalid_argument&) { rejected = true; }
    check(rejected);
    std::cout << "Native core checks passed\n";
    return 0;
  } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
