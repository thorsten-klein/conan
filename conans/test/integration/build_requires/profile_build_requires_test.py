import os
import platform
import unittest
import six

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, GenConanfile


tool_conanfile_1 = """
import os
from conans import ConanFile

class mytool(ConanFile):
    name = "tool1"
    version = "0.1"
    exports_sources = "mytool*"

    def package(self):
        self.copy("mytool*")

    def package_info(self):
        self.buildenv_info.append_path("PATH", self.package_folder)
"""

tool_conanfile_2 = """
import os
from conans import ConanFile

class mytool(ConanFile):
    pass
"""

tool_conanfile_3 = """
import os
from conans import ConanFile

class mytool(ConanFile):
    build_requires = "tool1/0.1@test/testchannel"
"""


consumer_conanfile_1 = """
from conans import ConanFile

class mylib(ConanFile):
    name = "mylib"
    version = "0.1"

    def build(self):
        self.run("mytool")
"""

consumer_conanfile_2 = """
from conans import ConanFile

class mylib(ConanFile):
    pass
"""

profile1 = """
[tool_requires]
tool1/0.1@test/testchannel
nonexistingpattern*: sometool/1.2@user/channel
"""

profile2 = """
[tool_requires]
tool1/0.1@test/testchannel
tool2/0.1@test/testchannel
nonexistingpattern*: sometool/1.2@user/channel
"""

profile3 = """
[tool_requires]
tool1/0.1@test/testchannel
tool2/0.1@test/testchannel
tool3/0.1@test/testchannel
nonexistingpattern*: sometool/1.2@user/channel
"""


class BuildRequiresTest(unittest.TestCase):

    def _create(self, client):
        name = "mytool.bat" if platform.system() == "Windows" else "mytool"
        client.save({CONANFILE: tool_conanfile_1,
                     name: "echo Hello World!"}, clean_first=True)
        os.chmod(os.path.join(client.current_folder, name), 0o777)
        client.run("export . --user=test --channel=testchannel")

    def test_profile_requires(self):
        client = TestClient()
        self._create(client)

        client.save({CONANFILE: consumer_conanfile_1,
                     "profile1.txt": profile1,
                     "profile2.txt": profile1}, clean_first=True)
        client.run("export . --user=test --channel=testchannel")

        client.run("install --reference=mylib/0.1@test/testchannel --profile ./profile1.txt --build missing")
        self.assertIn("Hello World!", client.out)

        client.run("install --reference=mylib/0.1@test/testchannel --profile ./profile2.txt --build")
        self.assertIn("Hello World!", client.out)

    def test_profile_open_requires(self):
        client = TestClient()
        self._create(client)

        client.save({CONANFILE: consumer_conanfile_1,
                     "profile.txt": profile1}, clean_first=True)

        client.run("build . --profile ./profile.txt --build missing")
        self.assertIn("Hello World!", client.out)

    def test_build_mode_requires(self):
        client = TestClient()
        self._create(client)

        client.save({CONANFILE: consumer_conanfile_1,
                     "profile.txt": profile1}, clean_first=True)

        client.run("install . --profile ./profile.txt", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'tool1/0.1@test/testchannel'", client.out)
        client.run("install . --profile ./profile.txt --build=Pythontool", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'tool1/0.1@test/testchannel'", client.out)
        client.run("install . --profile ./profile.txt --build=*tool1")
        self.assertIn("tool1/0.1@test/testchannel: Generated conaninfo.txt", client.out)

        # now remove packages, ensure --build=missing also creates them
        client.run('remove "*" -p -f')
        client.run("install . --profile ./profile.txt --build=missing")
        self.assertIn("tool1/0.1@test/testchannel: Generated conaninfo.txt", client.out)

    def test_profile_test_requires(self):
        client = TestClient()
        self._create(client)

        test_conanfile = """
import os
from conans import ConanFile, tools

class Testmylib(ConanFile):

    def build(self):
        self.run("mytool")

    def test(self):
        pass
        """
        client.save({CONANFILE: consumer_conanfile_1,
                     "test_package/conanfile.py": test_conanfile,
                     "profile1.txt": profile1,
                     "profile2.txt": profile2}, clean_first=True)

        client.run("create . test/testchannel --profile ./profile1.txt --build missing")
        self.assertEqual(2, str(client.out).splitlines().count("Hello World!"))

    def test_consumer_patterns(self):
        client = TestClient()
        self._create(client)

        test_conanfile = """
import os
from conans import ConanFile, tools

class Testmylib(ConanFile):

    def build(self):
        self.run("mytool")
    def test(self):
        pass
        """
        consumer_conanfile_1 = """
import os
from conans import ConanFile, tools

class mylib(ConanFile):
    name = "mylib"
    version = "0.1"


"""
        test_profile = """
[tool_requires]
&: tool1/0.1@test/testchannel
nonexistingpattern*: sometool/1.2@user/channel
"""
        client.save({CONANFILE: consumer_conanfile_1,
                     "test_package/conanfile.py": test_conanfile,
                     "profile.txt": test_profile}, clean_first=True)

        client.run("create . test/testchannel --profile=./profile.txt --build=missing")
        self.assertEqual(1, str(client.out).splitlines().count("Hello World!"))

    def test_build_requires_options(self):
        client = TestClient()
        client.save({CONANFILE: GenConanfile("mytool", "0.1")})
        client.run("export . --user=test --channel=testchannel")

        conanfile = """
from conans import ConanFile, tools

class mylib(ConanFile):
    name = "mylib"
    version = "0.1"
    build_requires = "mytool/0.1@test/testchannel"
    options = {"coverage": [True, False]}
    def build(self):
        self.output.info("Coverage %s" % self.options.coverage)
"""
        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("build . -o mylib:coverage=True --build missing")
        self.assertIn("mytool/0.1@test/testchannel from local cache", client.out)
        self.assertIn("mytool/0.1@test/testchannel: Calling build()", client.out)
        self.assertIn("conanfile.py (mylib/0.1): Coverage True", client.out)

        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("build . -o coverage=True")
        self.assertIn("mytool/0.1@test/testchannel from local cache", client.out)
        self.assertIn("mytool/0.1@test/testchannel: Already installed!", client.out)
        self.assertIn("conanfile.py (mylib/0.1): Coverage True", client.out)

    def test_multiple_tool_requires(self):
        client = TestClient()
        self._create(client)
        
        client.save({"conanfile_tool1.py": tool_conanfile_2,
                     "conanfile_tool2.py": tool_conanfile_2,
                     "conanfile_tool3.py": tool_conanfile_2,
                     "conanfile_consumer.py": consumer_conanfile_2,
                     "testprofile.txt": profile3}, clean_first=True)

        client.run("export conanfile_tool1.py --name=tool1 --version=0.1 --user=test --channel=testchannel")
        client.run("export conanfile_tool2.py --name=tool2 --version=0.1 --user=test --channel=testchannel")
        client.run("export conanfile_tool3.py --name=tool3 --version=0.1 --user=test --channel=testchannel")
        
        # TODO: right behavior that tool1, tool2 and tool3 are not built???
        for profiles in ["-pr:b=testprofile.txt"]: # no effect since there is no build_require at the moment
            client.run("create conanfile_consumer.py consumer/0.1@test/testchannel --build='*' -pr:b=default -pr:h=default {profiles}".format(profiles=profiles))
            self.assertNotIn("tool1/0.1@test/testchannel: Forced build from source", client.out) # build_requires from profile needs to  be built first
            self.assertNotIn("tool1/0.1@test/testchannel: Created package", client.out) 
            self.assertNotIn("tool2/0.1@test/testchannel: Forced build from source", client.out) # build_requires from profile needs to  be built first
            self.assertNotIn("tool2/0.1@test/testchannel: Created package", client.out)
            self.assertNotIn("tool3/0.1@test/testchannel: Forced build from source", client.out) # build_requires from profile needs to  be built first
            self.assertNotIn("tool3/0.1@test/testchannel: Created package", client.out)
            self.assertIn("consumer/0.1@test/testchannel: Created package", client.out)


        for profiles in ["-pr:h=testprofile.txt"]:
            client.run("create conanfile_consumer.py consumer/0.1@test/testchannel --build='*' -pr:b=default -pr:h=default {profiles}".format(profiles=profiles))
            self.assertIn("tool1/0.1@test/testchannel: Forced build from source", client.out) # build_requires from profile needs to  be built first
            self.assertIn("tool1/0.1@test/testchannel: Created package", client.out) 
            self.assertIn("tool2/0.1@test/testchannel: Forced build from source", client.out) # build_requires from profile needs to  be built first
            self.assertIn("tool2/0.1@test/testchannel: Created package", client.out)
            self.assertIn("tool3/0.1@test/testchannel: Forced build from source", client.out) # build_requires from profile needs to  be built first
            self.assertIn("tool3/0.1@test/testchannel: Created package", client.out)
            self.assertIn("consumer/0.1@test/testchannel: Created package", client.out)


        for profiles in ["-pr:b=testprofile.txt -pr:h=testprofile.txt"]:
            with six.assertRaisesRegex(self, Exception, "graph loop"):
                client.run("create conanfile_consumer.py consumer/0.1@test/testchannel --build='*' -pr:b=default -pr:h=default {profiles}".format(profiles=profiles))

     
    def test_multiple_tool_requires_new1(self):
        client = TestClient()
        self._create(client)
        profile3 = """
[tool_requires]
&+: tool1/0.1@test/testchannel
&+: tool2/0.1@test/testchannel
&+: tool3/0.1@test/testchannel
nonexistingpattern*: sometool/1.2@user/channel
"""
        client.save({"conanfile_tool1.py": tool_conanfile_2,
                     "conanfile_tool2.py": tool_conanfile_2,
                     "conanfile_tool3.py": tool_conanfile_2,
                     "conanfile_consumer.py": consumer_conanfile_2,
                     "testprofile.txt": profile3}, clean_first=True)

        client.run("export conanfile_tool1.py --name=tool1 --version=0.1 --user=test --channel=testchannel")
        client.run("export conanfile_tool2.py --name=tool2 --version=0.1 --user=test --channel=testchannel")
        client.run("export conanfile_tool3.py --name=tool3 --version=0.1 --user=test --channel=testchannel")
        
        for index, profiles in enumerate(["-pr:h=testprofile.txt",
                                          "-pr:b=testprofile.txt -pr:h=testprofile.txt"]):
            graphfile = "mygraph%s" % index
            client.run("info conanfile_consumer.py --graph={graphfile} -pr:b=default -pr:h=default {profiles}".format(profiles=profiles, graphfile=graphfile))
            contents = open(os.path.join(client.current_folder, graphfile)).read()
            self.assertIn('conanfile_consumer.py" -> "tool1/0.1@test/testchannel"', contents)
            self.assertIn('conanfile_consumer.py" -> "tool2/0.1@test/testchannel"', contents)
            self.assertIn('conanfile_consumer.py" -> "tool3/0.1@test/testchannel"', contents)
            
    def test_multiple_tool_requires_new2(self):
        client = TestClient()
        self._create(client)
        profile3 = """
[tool_requires]
&+: tool1/0.1@test/testchannel
&+: tool2/0.1@test/testchannel
*: tool3/0.1@test/testchannel
nonexistingpattern*: sometool/1.2@user/channel
"""
        client.save({"conanfile_tool1.py": tool_conanfile_2,
                     "conanfile_tool2.py": tool_conanfile_2,
                     "conanfile_tool3.py": tool_conanfile_2,
                     "conanfile_consumer.py": consumer_conanfile_2,
                     "testprofile.txt": profile3}, clean_first=True)

        client.run("export conanfile_tool1.py --name=tool1 --version=0.1 --user=test --channel=testchannel")
        client.run("export conanfile_tool2.py --name=tool2 --version=0.1 --user=test --channel=testchannel")
        client.run("export conanfile_tool3.py --name=tool3 --version=0.1 --user=test --channel=testchannel")
        
        graphfile = "mygraph"

        profiles="-pr:b=testprofile.txt"
        client.run("info conanfile_consumer.py --graph={graphfile} -pr:b=default -pr:h=default {profiles}".format(profiles=profiles, graphfile=graphfile))
        contents = open(os.path.join(client.current_folder, graphfile)).read()
        self.assertNotIn('conanfile_consumer.py" -> "tool1/0.1@test/testchannel"', contents)
        self.assertNotIn('conanfile_consumer.py" -> "tool2/0.1@test/testchannel"', contents)
        self.assertNotIn('conanfile_consumer.py" -> "tool3/0.1@test/testchannel"', contents)
        self.assertNotIn('"tool1/0.1@test/testchannel" -> "tool3/0.1@test/testchannel"', contents)
        self.assertNotIn('"tool2/0.1@test/testchannel" -> "tool3/0.1@test/testchannel"', contents)
        
        
        profiles="-pr:h=testprofile.txt"
        client.run("info conanfile_consumer.py --graph={graphfile} -pr:b=default -pr:h=default {profiles}".format(profiles=profiles, graphfile=graphfile))
        contents = open(os.path.join(client.current_folder, graphfile)).read()
        self.assertIn('conanfile_consumer.py" -> "tool1/0.1@test/testchannel"', contents)
        self.assertIn('conanfile_consumer.py" -> "tool2/0.1@test/testchannel"', contents)
        self.assertIn('conanfile_consumer.py" -> "tool3/0.1@test/testchannel"', contents)
        self.assertNotIn('"tool1/0.1@test/testchannel" -> "tool3/0.1@test/testchannel"', contents)
        self.assertNotIn('"tool2/0.1@test/testchannel" -> "tool3/0.1@test/testchannel"', contents)
        
        
        profiles="-pr:b=testprofile.txt -pr:h=testprofile.txt"
        client.run("info conanfile_consumer.py --graph={graphfile} -pr:b=default -pr:h=default {profiles}".format(profiles=profiles, graphfile=graphfile))
        contents = open(os.path.join(client.current_folder, graphfile)).read()
        self.assertIn('conanfile_consumer.py" -> "tool1/0.1@test/testchannel"', contents)
        self.assertIn('conanfile_consumer.py" -> "tool2/0.1@test/testchannel"', contents)
        self.assertIn('conanfile_consumer.py" -> "tool3/0.1@test/testchannel"', contents)
        self.assertIn('"tool1/0.1@test/testchannel" -> "tool3/0.1@test/testchannel"', contents)
        self.assertIn('"tool2/0.1@test/testchannel" -> "tool3/0.1@test/testchannel"', contents)
        
        
        
        
            
    def test_forced_build(self):
        client = TestClient()
        self._create(client)

        test_profile = """
[tool_requires]
tool1/0.1@test/testchannel
"""
        client.save({"conanfile_tool1.py": tool_conanfile_2,
                     "conanfile_consumer.py": consumer_conanfile_2,
                     "testprofile.txt": test_profile}, clean_first=True)

        client.run("export conanfile_tool1.py --name=tool1 --version=0.1 --user=test --channel=testchannel")
        
        
        for build in ["--build=consumer --build=tool1",
                      #"--build=all", # not supported anymore??
                      "--build='*'"
                     ]:
            for profiles in ["-pr:b=testprofile.txt -pr:h=testprofile.txt",
                             "-pr:h=testprofile.txt",
                             #"-pr:b=testprofile.txt" # no effect since there is no build_require at the moment
                            ]:
                client.run("create conanfile_consumer.py consumer/0.1@test/testchannel -pr:b=default -pr:h=default {profiles} {build}".format(profiles=profiles, build=build))
                self.assertIn("tool1/0.1@test/testchannel: Forced build from source", client.out) # build_requires from profile needs to  be built first
                self.assertIn("tool1/0.1@test/testchannel: Created package", client.out) 
                self.assertIn("consumer/0.1@test/testchannel: Forced build from source", client.out)
                self.assertIn("consumer/0.1@test/testchannel: Created package", client.out)
            
            
    def test_consumer_patterns_negotiated(self):
        client = TestClient()
        self._create(client)

        test_profile = """
[tool_requires]
tool1/0.1@test/testchannel
!tool1/*: tool2/0.1@test/testchannel
!*: tool3/0.1@test/testchannel
"""
        client.save({"conanfile_tool1.py": tool_conanfile_2,
                     "conanfile_tool2.py": tool_conanfile_3,
                     "conanfile_tool3.py": tool_conanfile_3,
                     "conanfile_consumer.py": consumer_conanfile_2,
                     "testprofile.txt": test_profile}, clean_first=True)

        client.run("export conanfile_tool1.py --name=tool1 --version=0.1 --user=test --channel=testchannel")
        client.run("export conanfile_tool2.py --name=tool2 --version=0.1 --user=test --channel=testchannel")
        client.run("export conanfile_tool3.py --name=tool3 --version=0.1 --user=test --channel=testchannel")
        
        for profiles in ["-pr:b=testprofile.txt -pr:h=testprofile.txt",
                         "-pr:h=testprofile.txt",
                         "-pr:b=testprofile.txt"
                        ]:
            client.run("create conanfile_consumer.py consumer/0.1@test/testchannel --build=consumer --build=tool1 --build=tool2 --build=tool3 -pr:b=testprofile.txt -pr:h=testprofile.txt -pr:b=default -pr:h=default {profiles}".format(profiles=profiles))
            self.assertIn("tool1/0.1@test/testchannel: Forced build from source", client.out)
            self.assertIn("tool1/0.1@test/testchannel: Created package", client.out)
            self.assertIn("tool2/0.1@test/testchannel: Forced build from source", client.out)
            self.assertIn("tool2/0.1@test/testchannel: Created package", client.out)
            self.assertNotIn("tool3/0.1@test/testchannel: Forced build from source", client.out)
            self.assertNotIn("tool3/0.1@test/testchannel: Created package", client.out)
            self.assertIn("consumer/0.1@test/testchannel: Forced build from source", client.out)
            self.assertIn("consumer/0.1@test/testchannel: Created package", client.out)