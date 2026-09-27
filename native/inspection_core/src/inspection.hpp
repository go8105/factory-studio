#pragma once
#include <nlohmann/json.hpp>
#include <string>
namespace vision {
struct Request { std::string sample; std::string roi; int threshold; int minArea; };
Request parseRequest(const nlohmann::json& document);
nlohmann::json inspect(const Request& request);
}
