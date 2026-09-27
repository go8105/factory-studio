#include "inspection.hpp"
#include <chrono>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
namespace {
constexpr std::size_t maxBytes = 65536;
void error(const char* code) { std::cout << nlohmann::json({{"version", 1}, {"error", {{"code", code}}}}).dump() << '\n' << std::flush; }
bool read(std::istream& input, std::string& text, bool line) {
  text.clear(); char c;
  while (input.get(c)) {
    if (line && c == '\n') return true;
    if (text.size() == maxBytes) throw std::length_error("Input too large");
    text += c;
  }
  if (input.bad()) throw std::runtime_error("Read failed");
  return !text.empty();
}
bool process(const std::string& text, bool timed) {
  try {
    const auto request = vision::parseRequest(nlohmann::json::parse(text));
    const auto start = std::chrono::steady_clock::now();
    auto result = vision::inspect(request);
    const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count();
    if (timed) result = nlohmann::json{{"result", result}, {"inspectionMs", ms}};
    std::cout << result.dump() << '\n' << std::flush;
    return true;
  } catch (const nlohmann::json::exception&) { error("INVALID_REQUEST"); }
    catch (const std::invalid_argument&) { error("INVALID_REQUEST"); }
    catch (const std::exception&) { error("INSPECTION_FAILED"); }
  return false;
}
}
int main(int argc, char** argv) {
  if (argc > 2) { error("INVALID_ARGUMENTS"); return 2; }
  const bool lines = argc == 2 && std::string(argv[1]) == "--ndjson";
  const bool timed = argc == 2 && std::string(argv[1]) == "--timed";
  std::ifstream file;
  std::istream* input = &std::cin;
  if (argc == 2 && !lines && !timed) {
    file.open(argv[1], std::ios::binary);
    if (!file) { error("INPUT_OPEN_FAILED"); return 2; }
    input = &file;
  }
  bool success = true, any = false;
  std::string text;
  try {
    while (read(*input, text, lines)) { any = true; if (!process(text, timed)) success = false; if (!lines) break; }
  } catch (const std::length_error&) { error("INPUT_TOO_LARGE"); return 2; }
    catch (const std::exception&) { error("INPUT_READ_FAILED"); return 2; }
  if (!any) { error("INVALID_REQUEST"); return 2; }
  return success && std::cout.good() ? 0 : 2;
}
