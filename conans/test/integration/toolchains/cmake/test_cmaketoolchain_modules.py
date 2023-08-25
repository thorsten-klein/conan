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
    "find_package_prefer_config", ["ON", "OFF", ""],
)
@pytest.mark.parametrize(
    "config_name_consumer", ["Findhello.cmake", "hello-config.cmake"]
)
@pytest.mark.parametrize(
    "config_name_hello", ["Findhello.cmake", "hello-config.cmake"]
)
@pytest.mark.parametrize(
    "cmake_consumer_path_mode", ["PREPEND", "APPEND"]
)
@pytest.mark.parametrize(
    "cmake_subfolder", ["cmake", "anyothername", "lib/cmake", "lib", "hello", "hello/cmake"]
)
#def test_cmaketoolchain_path_find_package_real_config_default(config_name_hello="hello-config.cmake", config_name_consumer="Findhello.cmake", find_package_prefer_config="ON"):
def test_cmaketoolchain_path_find_package_real_config_default(config_name_hello, config_name_consumer, find_package_prefer_config, cmake_consumer_path_mode,cmake_subfolder):
    # print("\n\n\n")
    # print("config_name_hello: %s" % config_name_hello)
    # print("config_name_consumer: %s" % config_name_consumer)
    # print("find_package_prefer_config: %s" % find_package_prefer_config)

    client = TestClient(path_with_spaces=False)

    find_hello = textwrap.dedent("""
        SET(hello_FOUND 1)
        MESSAGE(STATUS "hello from {component}:{filename}")
        """)
    conanfile_hello = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy
        class TestConan(ConanFile):
            name = "hello"
            version = "0.1"
            exports_sources = "*"
            def package(self):
                copy(self, "*", self.source_folder, self.package_folder)
            def package_info(self):
                self.cpp_info.builddirs.append("{subfolder}")
        """.format(subfolder=cmake_subfolder))
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

            def generate(self):
                tc = CMakeToolchain(self)
                tc.blocks["find_paths"].values["find_package_prefer_config"] = "{value}"
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.install()
        """.format(value=find_package_prefer_config))
    cmake_consumer = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.15)
        project(MyHello CXX)
        list(%s CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/mymodules)
        list(%s CMAKE_PREFIX_PATH ${CMAKE_CURRENT_SOURCE_DIR}/mymodules)
        message(STATUS "CMAKE_FIND_PACKAGE_PREFER_CONFIG '${CMAKE_FIND_PACKAGE_PREFER_CONFIG}'")
        find_package(hello REQUIRED)
        """ % (cmake_consumer_path_mode, cmake_consumer_path_mode))

    client.save({"hello/conanfile.py": conanfile_hello,
                 "hello/%s/%s" % (cmake_subfolder, config_name_hello): find_hello.format(component="hello", filename=config_name_hello),
                 "consumer/conanfile.py": conanfile_consumer,
                 "consumer/CMakeLists.txt": cmake_consumer,
                 "consumer/mymodules/%s" % config_name_consumer: find_hello.format(component="consumer", filename=config_name_consumer),
                 })

    client.run("export hello")
    with client.chdir("consumer"):
        client.run("install . -pr:h=default --build=missing")
        with client.chdir("build"):
            client.run_command("cat ../conan_toolchain.cmake")
            #print(client.out)
            client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
            #print(client.out)
    filenames = (config_name_hello, config_name_consumer)
    if cmake_consumer_path_mode == "PREPEND":
        if config_name_hello == config_name_consumer:
            expected_component = "consumer" # path was prepended
        if find_package_prefer_config == "ON":
            if filenames == ("hello-config.cmake", "Findhello.cmake"):
                expected_component = "hello"
            elif filenames == ("Findhello.cmake", "hello-config.cmake"):
                expected_component = "consumer"
        else: # OFF = same as default behavior
            if filenames == ("hello-config.cmake", "Findhello.cmake"):
                expected_component = "consumer"
            elif filenames == ("Findhello.cmake", "hello-config.cmake"):
                expected_component = "hello"
    elif cmake_consumer_path_mode == "APPEND":
        if config_name_hello == config_name_consumer:
            expected_component = "hello" # path was appended
        if find_package_prefer_config == "ON":
            if filenames == ("hello-config.cmake", "Findhello.cmake"):
                expected_component = "hello"
            elif filenames == ("Findhello.cmake", "hello-config.cmake"):
                expected_component = "consumer"
        else: # OFF = same as default behavior
            if filenames == ("hello-config.cmake", "Findhello.cmake"):
                expected_component = "consumer"
            elif filenames == ("Findhello.cmake", "hello-config.cmake"):
                expected_component = "hello"
    expected_filename = config_name_hello if (expected_component == "hello") else config_name_consumer
    assert "hello from {component}:{filename}".format(component=expected_component, filename=expected_filename) in client.out
    assert "CMAKE_FIND_PACKAGE_PREFER_CONFIG '%s'" % find_package_prefer_config in client.out
