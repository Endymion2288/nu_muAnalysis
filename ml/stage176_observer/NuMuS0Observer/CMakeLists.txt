atlas_subdir(NuMuS0Observer)
find_package(Geant4 REQUIRED)
find_library(STAGE176_CALO FaserCaloSimEvent HINTS $ENV{FASER_CALYPSO_RUN}/lib REQUIRED)
find_library(STAGE176_SCINT ScintSimEvent HINTS $ENV{FASER_CALYPSO_RUN}/lib REQUIRED)
atlas_add_component(NuMuS0Observer src/*.cxx
    INCLUDE_DIRS ${GEANT4_INCLUDE_DIRS} $ENV{FASER_CALYPSO_RUN}/include
    LINK_LIBRARIES ${GEANT4_LIBRARIES} ${STAGE176_CALO} ${STAGE176_SCINT} AthenaBaseComps GaudiKernel G4AtlasToolsLib StoreGateLib GeneratorObjects HitManagement)
