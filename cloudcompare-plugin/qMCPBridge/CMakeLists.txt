# qMCPBridge is built inside a CloudCompare source tree.
option( PLUGIN_STANDARD_QMCP_BRIDGE "Install the MCP live-control bridge plugin" OFF )

if ( PLUGIN_STANDARD_QMCP_BRIDGE )
    project( QMCP_BRIDGE_PLUGIN )

    AddPlugin( NAME ${PROJECT_NAME} )

    # Use the same Qt major version as the host CloudCompare build.
    if ( TARGET Qt6::Core )
        set( QMCP_QT_PACKAGE Qt6 )
    elseif ( TARGET Qt5::Core )
        set( QMCP_QT_PACKAGE Qt5 )
    else()
        message( FATAL_ERROR "qMCPBridge requires CloudCompare's Qt targets" )
    endif()
    find_package( ${QMCP_QT_PACKAGE} REQUIRED COMPONENTS Network )

    target_sources( ${PROJECT_NAME}
        PRIVATE
            ${CMAKE_CURRENT_LIST_DIR}/qMCPBridge.qrc
            ${CMAKE_CURRENT_LIST_DIR}/include/qMCPBridge.h
            ${CMAKE_CURRENT_LIST_DIR}/include/qMCPFusionWorkflow.h
            ${CMAKE_CURRENT_LIST_DIR}/src/qMCPBridge.cpp
            ${CMAKE_CURRENT_LIST_DIR}/src/qMCPFusionWorkflow.cpp
    )

    target_include_directories( ${PROJECT_NAME}
        PRIVATE
            ${CMAKE_CURRENT_LIST_DIR}/include
    )

    # CloudCompare 2.13.x does not populate QCoreApplication::applicationVersion().
    # Record the source-tree version used to build the plugin as an explicitly
    # build-time fallback for runtime reporting.
    set( QMCP_CLOUDCOMPARE_BUILD_VERSION "" )
    if ( DEFINED CloudCompare_VERSION AND NOT "${CloudCompare_VERSION}" STREQUAL "" )
        set( QMCP_CLOUDCOMPARE_BUILD_VERSION "${CloudCompare_VERSION}" )
    elseif ( EXISTS "${CloudCompareProjects_SOURCE_DIR}/qCC/CMakeLists.txt" )
        file( STRINGS "${CloudCompareProjects_SOURCE_DIR}/qCC/CMakeLists.txt"
              QMCP_CLOUDCOMPARE_PROJECT_LINE
              REGEX "project\\( *CloudCompare +VERSION +[0-9]+\\.[0-9]+\\.[0-9]+" )
        if ( QMCP_CLOUDCOMPARE_PROJECT_LINE )
            string( REGEX MATCH "[0-9]+\\.[0-9]+\\.[0-9]+"
                    QMCP_CLOUDCOMPARE_BUILD_VERSION
                    "${QMCP_CLOUDCOMPARE_PROJECT_LINE}" )
        endif()
    endif()
    if ( NOT "${QMCP_CLOUDCOMPARE_BUILD_VERSION}" STREQUAL "" )
        target_compile_definitions( ${PROJECT_NAME} PRIVATE
            QMCP_CLOUDCOMPARE_BUILD_VERSION="${QMCP_CLOUDCOMPARE_BUILD_VERSION}" )
    endif()

    # AddPlugin in older releases uses the plain target_link_libraries
    # signature. Appending the dependency works with either helper version.
    set_property( TARGET ${PROJECT_NAME} APPEND PROPERTY
        LINK_LIBRARIES ${QMCP_QT_PACKAGE}::Network QCC_IO_LIB QCC_DB_LIB CCCoreLib )
endif()
