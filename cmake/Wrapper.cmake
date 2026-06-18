# ---- Shared Wrapper configuration ----

set(Python3_FIND_REGISTRY "NEVER")
set(Python3_FIND_VIRTUALENV "FIRST")
set(Python3_FIND_STRATEGY "LOCATION")

set(LIVE2D_PY_LIMITED_API "0x03020000" CACHE STRING
    "Py_LIMITED_API value used for live2d Python wrappers")

if(DEFINED PYTHON_INSTALLATION_PATH AND NOT "${PYTHON_INSTALLATION_PATH}" STREQUAL "")
    message(STATUS "Using PYTHON_INSTALLATION_PATH=${PYTHON_INSTALLATION_PATH}")
    set(Python3_ROOT_DIR "${PYTHON_INSTALLATION_PATH}")
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.SABIModule)

if(Python3_VERSION VERSION_LESS "3.2")
    message(FATAL_ERROR "live2d Python wrappers require Python 3.2 or newer for the stable ABI")
endif()

message(STATUS "Python3 executable: ${Python3_EXECUTABLE}")
message(STATUS "Python3 version: ${Python3_VERSION}")
message(STATUS "Python3 include dirs: ${Python3_INCLUDE_DIRS}")
message(STATUS "Py_LIMITED_API: ${LIVE2D_PY_LIMITED_API}")

function(target_link_limited_python TARGET)
    target_compile_definitions(${TARGET} PRIVATE Py_LIMITED_API=${LIVE2D_PY_LIMITED_API})
    target_link_libraries(${TARGET} PRIVATE Python3::SABIModule)
endfunction()

# Helper: set output name (.pyd on Windows, .so elsewhere) and OUTPUT_NAME
function(set_wrapper_output TARGET baseName)
    if(CMAKE_SYSTEM_NAME MATCHES "Windows")
        set_target_properties(${TARGET} PROPERTIES
            SUFFIX ".pyd" PREFIX "" OUTPUT_NAME "${baseName}")
    elseif(CMAKE_SYSTEM_NAME MATCHES "Darwin")
        set_target_properties(${TARGET} PROPERTIES
            SUFFIX ".so" PREFIX "" OUTPUT_NAME "${baseName}")
    else()
        set_target_properties(${TARGET} PROPERTIES
            SUFFIX ".so" PREFIX "" OUTPUT_NAME "${baseName}")
    endif()
endfunction()
