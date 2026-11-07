atlas_subdir(NuMuBoundaryObserver)
find_package(Geant4 REQUIRED)
find_library(STAGE135_CALO FaserCaloSimEvent HINTS $ENV{FASER_CALYPSO_RUN}/lib REQUIRED)
find_library(STAGE142_SCINT ScintSimEvent HINTS $ENV{FASER_CALYPSO_RUN}/lib REQUIRED)
atlas_add_component(NuMuBoundaryObserver src/*.cxx
    INCLUDE_DIRS ${GEANT4_INCLUDE_DIRS} $ENV{FASER_CALYPSO_RUN}/include
    LINK_LIBRARIES ${GEANT4_LIBRARIES} ${STAGE135_CALO} ${STAGE142_SCINT} AthenaBaseComps GaudiKernel G4AtlasToolsLib StoreGateLib GeneratorObjects HitManagement)
