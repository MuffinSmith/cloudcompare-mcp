# qMCPBridge is built inside a CloudCompare source tree.
option( PLUGIN_STANDARD_QMCP_BRIDGE "Install the MCP live-control bridge plugin" OFF )

if ( PLUGIN_STANDARD_QMCP_BRIDGE )
    project( QMCP_BRIDGE_PLUGIN )

    AddPlugin( NAME ${PROJECT_NAME} )

    find_package( Qt6 REQUIRED COMPONENTS Network )

    target_sources( ${PROJECT_NAME}
        PRIVATE
            ${CMAKE_CURRENT_LIST_DIR}/include/qMCPBridge.h
            ${CMAKE_CURRENT_LIST_DIR}/src/qMCPBridge.cpp
    )

    target_include_directories( ${PROJECT_NAME}
        PRIVATE
            ${CMAKE_CURRENT_LIST_DIR}/include
    )

    target_link_libraries( ${PROJECT_NAME}
        PRIVATE
            Qt6::Network
    )
endif()
