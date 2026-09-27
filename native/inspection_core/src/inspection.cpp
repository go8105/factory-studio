#include "inspection.hpp"
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <cmath>
#include <stdexcept>
#include <vector>
namespace vision {
namespace {
constexpr int width = 160, height = 100;
int integer(const nlohmann::json& value, int low, int high) {
  if (!value.is_number()) throw std::invalid_argument("Expected integer");
  const double number = value.get<double>();
  if (!std::isfinite(number) || std::floor(number) != number || number < low || number > high)
    throw std::invalid_argument("Integer out of range");
  return static_cast<int>(number);
}
void validate(const Request& r) {
  if ((r.sample != "normal" && r.sample != "foreign" && r.sample != "lighting") ||
      (r.roi != "full" && r.roi != "center") || r.threshold < 0 || r.threshold > 255 ||
      r.minArea < 1 || r.minArea > width * height) throw std::invalid_argument("Invalid inspection request");
}
}
Request parseRequest(const nlohmann::json& document) {
  const auto& d = document.is_object() && document.contains("request") ? document.at("request") : document;
  if (!d.is_object()) throw std::invalid_argument("Expected request object");
  integer(d.at("version"), 1, 1);
  const auto& recipe = d.at("recipe");
  Request r{d.at("sample").get<std::string>(), recipe.at("roi").get<std::string>(),
            integer(recipe.at("threshold"), 0, 255), integer(recipe.at("minArea"), 1, width * height)};
  validate(r);
  return r;
}
nlohmann::json inspect(const Request& r) {
  validate(r);
  cv::Mat gray(height, width, CV_8UC1), truth = cv::Mat::zeros(height, width, CV_8UC1);
  for (int y = 0; y < height; ++y) for (int x = 0; x < width; ++x) {
    auto& pixel = gray.at<unsigned char>(y, x);
    pixel = static_cast<unsigned char>(r.sample == "lighting" && x < 40 ? 110 : 210 + ((x + y) % 7));
    if (x >= 75 && x < 77 && y >= 25 && y < 27) pixel = 55;
    if (r.sample != "normal" && ((x >= 55 && x < 65 && y >= 40 && y < 48) ||
        (x >= 120 && x < 126 && y >= 65 && y < 71))) {
      pixel = 45; truth.at<unsigned char>(y, x) = 1;
    }
  }
  const cv::Rect roi = r.roi == "full" ? cv::Rect(0, 0, width, height) : cv::Rect(40, 20, 80, 60);
  cv::Mat candidates, mask = cv::Mat::zeros(height, width, CV_8UC1);
  cv::compare(gray, cv::Scalar(r.threshold), candidates, cv::CMP_LT);
  candidates(roi).copyTo(mask(roi));
  cv::Mat labels, stats, centroids;
  // SAUF assigns labels in row-major order, matching the browser's scan order.
  const int count = cv::connectedComponentsWithStats(mask, labels, stats, centroids, 4, CV_32S, cv::CCL_SAUF);
  std::vector<bool> accepted(static_cast<std::size_t>(count), false);
  auto regions = nlohmann::json::array();
  for (int label = 1; label < count; ++label) {
    const int area = stats.at<int>(label, cv::CC_STAT_AREA);
    if (area < r.minArea) continue;
    accepted[static_cast<std::size_t>(label)] = true;
    regions.push_back({{"x", stats.at<int>(label, cv::CC_STAT_LEFT)}, {"y", stats.at<int>(label, cv::CC_STAT_TOP)},
      {"width", stats.at<int>(label, cv::CC_STAT_WIDTH)}, {"height", stats.at<int>(label, cv::CC_STAT_HEIGHT)}, {"area", area}});
  }
  int falsePixels = 0, missedPixels = 0, excludedPixels = 0;
  for (int y = 0; y < height; ++y) for (int x = 0; x < width; ++x) {
    const bool actual = truth.at<unsigned char>(y, x) != 0;
    if (!roi.contains(cv::Point(x, y))) { excludedPixels += actual; continue; }
    const bool detected = accepted[static_cast<std::size_t>(labels.at<int>(y, x))];
    falsePixels += detected && !actual;
    missedPixels += !detected && actual;
  }
  return {{"version", 1}, {"source", "synthetic-opencv-cpp-v1"}, {"status", regions.empty() ? "OK" : "NG"},
          {"regions", regions}, {"falsePixels", falsePixels}, {"missedPixels", missedPixels}, {"excludedPixels", excludedPixels}};
}
}
