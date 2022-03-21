cmake_minimum_required(VERSION 2.8)

include(RezBuild)
include(ExternalProject)

ExternalProject_add(
  ${PROJECT_NAME}
  PREFIX ${PROJECT_NAME}
  GIT_REPOSITORY git@github.com:mottosso/Qt.py.git
  GIT_TAG ${QT_PY_VERSION}
  CONFIGURE_COMMAND ""
  BUILD_COMMAND ""
  INSTALL_COMMAND ""
)

rez_install_files(
  "build/Qt_py/src/Qt_py/Qt.py"
  RELATIVE "build/Qt_py/src/Qt_py" 
  DESTINATION "python/Qt_py")
