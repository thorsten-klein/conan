import json
import os
import platform
import textwrap

import pytest
from mock import mock

from conan.tools.cmake.presets import load_cmake_presets
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import rmdir

@pytest.mark.parametrize(
    "prefer_config", [None, True, False, "None", ""]
)
def test_cmaketoolchain_path_find_package_real_config_default(prefer_config):
    client = TestClient(path_with_spaces=False)
    find_hello = textwrap.dedent("""
        MESSAGE(STATUS "hello from hello")
        """)
    conanfile_hello= textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy
        class TestConan(ConanFile):
            name = "hello"
            version = "0.1"
            exports_sources = "*"
            def package(self):
                copy(self, "*", self.source_folder, self.package_folder)
            def package_info(self):
                self.cpp_info.builddirs.append("cmake")
        """)
    
    find_cmake_helper_hello = textwrap.dedent("""
        MESSAGE(STATUS "hello from cmake-helper hello")
        find_package(hello CONFIG)
        """)
    conanfile_cmake_helpers = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy
        class TestConan(ConanFile):
            name = "cmake-helpers"
            version = "0.1"
            exports_sources = "*"
            def package(self):
                copy(self, "*", self.source_folder, self.package_folder)
            def package_info(self):
                self.cpp_info.builddirs.append("cmake")
        """)
    
    conanfile_consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain
        import os
        class TestConan(ConanFile):
            name = "consumer"
            version = "1.0.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "*"
            requires = "hello/0.1@"
            tool_requires = "cmake-helpers/0.1@"

            def generate(self):
                tc = CMakeToolchain(self)
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.install()
        """)

    profile = textwrap.dedent("""
        include(default)
        [conf]
        tools.cmake.cmaketoolchain:find_package_prefer_config={}
        """)
    
    cmake_consumer = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.15)
        project(MyHello CXX)
        message(STATUS "CMAKE_FIND_PACKAGE_PREFER_CONFIG '${CMAKE_FIND_PACKAGE_PREFER_CONFIG}'")
        #set(CMAKE_FIND_DEBUG_MODE TRUE)
        find_package(hello REQUIRED)
        """)

    client.save({"hello/conanfile.py": conanfile_hello,
                 "hello/cmake/hello-config.cmake": find_hello,
                 "cmake-helpers/conanfile.py": conanfile_cmake_helpers,
                 "cmake-helpers/cmake/Findhello.cmake": find_cmake_helper_hello,
                 "consumer/conanfile.py": conanfile_consumer,
                 "consumer/CMakeLists.txt": cmake_consumer,
                 "profile": profile.format(prefer_config)
                 })

    client.run("export hello")
    client.run("export cmake-helpers")
    cmd = "create consumer --build=missing"
    if prefer_config is not None:
        cmd += " -pr:h=profile"
    client.run(cmd)

    assert "hello from hello" in client.out
    if prefer_config not in [True]:
        assert "hello from cmake-helper hello" in client.out

    if prefer_config in [True]:
        assert "CMAKE_FIND_PACKAGE_PREFER_CONFIG 'ON'" in client.out
    elif prefer_config in [False]:
        assert "CMAKE_FIND_PACKAGE_PREFER_CONFIG 'OFF'" in client.out
    else:
        assert "CMAKE_FIND_PACKAGE_PREFER_CONFIG ''" in client.out
