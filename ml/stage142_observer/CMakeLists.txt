cmake_minimum_required(VERSION 3.10)
project(NuMuBoundaryObserver VERSION 1.0 LANGUAGES C CXX)
find_package(Athena REQUIRED)
atlas_project(USE Athena ${Athena_VERSION})
