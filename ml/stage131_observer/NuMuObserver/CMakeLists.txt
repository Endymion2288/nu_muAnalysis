atlas_subdir(NuMuObserver)
find_package(Geant4 REQUIRED)
find_library(STAGE131_CALO FaserCaloSimEvent HINTS $ENV{FASER_CALYPSO_RUN}/lib REQUIRED)
atlas_add_component(NuMuObserver src/*.cxx
    INCLUDE_DIRS ${GEANT4_INCLUDE_DIRS} $ENV{FASER_CALYPSO_RUN}/include
    LINK_LIBRARIES ${GEANT4_LIBRARIES} ${STAGE131_CALO} AthenaBaseComps GaudiKernel G4AtlasToolsLib StoreGateLib GeneratorObjects HitManagement)
