cmake_minimum_required(VERSION 3.15)
project(gaia_lookup LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(IOC_GaiaLib REQUIRED)

add_executable(gaia_lookup src/gaia_lookup.cpp)
target_link_libraries(gaia_lookup PRIVATE IOC_GaiaLib::ioc_gaialib)

# Install target
install(TARGETS gaia_lookup RUNTIME DESTINATION bin)
