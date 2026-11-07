#include "GaudiKernel/Bootstrap.h"
#include "GaudiKernel/ISvcLocator.h"
#include "StoreGate/StoreGateSvc.h"
#include "GeoModelFaserUtilities/GeoModelExperiment.h"
#include "GeoModelKernel/GeoBox.h"
#include "GeoModelKernel/GeoVPhysVol.h"
#include "GeoModelKernel/GeoPhysVol.h"
#include "GeoModelKernel/GeoLogVol.h"
#include "GeoModelKernel/GeoMaterial.h"
#include <algorithm>
#include <functional>
#include <stdexcept>
#include <string>
#include <vector>

namespace Stage129 {
struct MaterialInterval {
    std::string volume, material;
    double low, high, radiationLength, interactionLength, density;
    int depth;
};
std::vector<MaterialInterval> centralMaterial() {
    StoreGateSvc* store = nullptr;
    if (Gaudi::svcLocator()->service("DetectorStore", store).isFailure())
        throw std::runtime_error("DetectorStore unavailable");
    const GeoModelExperiment* experiment = nullptr;
    if (store->retrieve(experiment, "FASER").isFailure())
        throw std::runtime_error("FASER geometry unavailable");
    std::vector<MaterialInterval> output;
    std::function<void(const GeoVPhysVol*, const GeoTrf::Transform3D&, int)> visit;
    visit = [&](const GeoVPhysVol* volume, const GeoTrf::Transform3D& transform, int depth) {
        const auto* logical = volume->getLogVol();
        const auto* box = dynamic_cast<const GeoBox*>(logical->getShape());
        if (box) {
            const auto inverse = transform.inverse();
            const GeoTrf::Vector3D origin = inverse * GeoTrf::Vector3D(0.,0.,0.);
            const GeoTrf::Vector3D direction = inverse.linear() * GeoTrf::Vector3D(0.,0.,1.);
            const double half[] = {box->getXHalfLength(),box->getYHalfLength(),box->getZHalfLength()};
            double low = -3200., high = -1300.;
            for (int axis=0; axis<3; ++axis) {
                if (std::abs(direction[axis]) < 1e-12) {
                    if (std::abs(origin[axis]) >= half[axis]) { high = low; break; }
                } else {
                    double a = (-half[axis]-origin[axis])/direction[axis];
                    double b = (half[axis]-origin[axis])/direction[axis];
                    if (a>b) std::swap(a,b);
                    low = std::max(low,a); high = std::min(high,b);
                }
            }
            if (high>low) {
                const auto* material = logical->getMaterial();
                output.push_back({logical->getName(),material->getName(),low,high,
                                  material->getRadLength(),material->getIntLength(),material->getDensity(),depth});
            }
        }
        for (unsigned int i=0; i<volume->getNChildVols(); ++i)
            visit(&*volume->getChildVol(i),transform*volume->getXToChildVol(i),depth+1);
    };
    visit(&*experiment->getPhysVol(),GeoTrf::Transform3D::Identity(),0);
    return output;
}
}
