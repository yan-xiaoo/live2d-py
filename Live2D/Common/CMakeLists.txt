set(LIVE2D_COMMON Common)

add_library(${LIVE2D_COMMON} STATIC 
    ${LIVE2D_ROOT}/Common/Log.cpp
    ${LIVE2D_ROOT}/Common/stb_impl.cpp
)

target_include_directories(${LIVE2D_COMMON} PUBLIC ${LIVE2D_ROOT}/Common)

add_library(Live2D::Common ALIAS ${LIVE2D_COMMON})

if(DEBUG_ENABLE_CALLSTACK)
    target_sources(${LIVE2D_COMMON} PRIVATE ${LIVE2D_ROOT}/Common/Debug.cpp)
    add_subdirectory(${LIVE2D_ROOT}/Common/backward)
    target_link_libraries(${LIVE2D_COMMON} PUBLIC Backward::Backward)
endif()