import unittest
import urllib2
from ftplib import FTP
from stubserver import StubServer, FTPStubServer
from StringIO import StringIO
from unittest import TestCase


class WebTest(TestCase):
    def setUp(self):
        self.server = StubServer(8998)
        self.server.run()

    def tearDown(self):
        self.server.stop()
        self.server.verify()  # this is redundant because stop includes verify

    def _make_request(self, url, method="GET", payload="", headers={}):
        self.opener = urllib2.OpenerDirector()
        self.opener.add_handler(urllib2.HTTPHandler())
        request = urllib2.Request(url, headers=headers, data=payload)
        request.get_method = lambda: method
        response = self.opener.open(request)
        response_code = getattr(response, 'code', -1)
        return (response, response_code)

    def test_get_with_file_call(self):
        f = open('data.txt', 'w')
        f.write("test file")
        f.close()
        self.server.expect(method="GET", url="/address/\d+$").and_return(mime_type="text/xml", file_content="./data.txt")
        response, response_code = self._make_request("http://localhost:8998/address/25", method="GET")
        expected = open("./data.txt", "r").read()
        try:
            self.assertEquals(expected, response.read())
        finally:
            response.close()

    def test_put_with_capture(self):
        capture = {}
        self.server.expect(method="PUT", url="/address/\d+$", data_capture=capture).and_return(reply_code=201)
        f, reply_code = self._make_request("http://localhost:8998/address/45", method="PUT", payload=str({"hello": "world", "hi": "mum"}))
        try:
            self.assertEquals("", f.read())
            captured = eval(capture["body"])
            self.assertEquals("world", captured["hello"])
            self.assertEquals("mum", captured["hi"])
            self.assertEquals(201, reply_code)
        finally:
            f.close()

    def test_post_with_data_and_no_body_response(self):
        self.server.expect(method="POST", url="address/\d+/inhabitant", data='<inhabitant name="Chris"/>').and_return(reply_code=204)
        f, reply_code = self._make_request("http://localhost:8998/address/45/inhabitant", method="POST", payload='<inhabitant name="Chris"/>')
        self.assertEquals(204, reply_code)

    def test_post_with_data_and_no_body_response(self):
        self.server.expect(method="POST", url="address/\d+/inhabitant", data='Twas brillig and the slithy toves').and_return(reply_code=204)
        f, reply_code = self._make_request("http://localhost:8998/address/45/inhabitant", method="POST", payload='Twas brillig and the slithy toves')
        self.assertEquals(204, reply_code)
        self.server.expect(method="GET", url="/monitor/server_status$").and_return(content="Four score and seven years ago", mime_type="text/html")
        try:
            self.server.stop()
        except Exception as e:
            self.assertEquals(-1, str(e).find('brillig'), str(e))

    def test_get_with_data(self):
        self.server.expect(method="GET", url="/monitor/server_status$").and_return(content="<html><body>Server is up</body></html>", mime_type="text/html")
        f, reply_code = self._make_request("http://localhost:8998/monitor/server_status", method="GET")
        try:
            self.assertTrue("Server is up" in f.read())
            self.assertEquals(200, reply_code)
        finally:
            f.close()

    def test_get_from_root(self):
        self.server.expect(method="GET", url="/$").and_return(content="<html><body>Server is up</body></html>", mime_type="text/html")
        f, reply_code = self._make_request("http://localhost:8998/", method="GET")
        try:
            self.assertTrue("Server is up" in f.read())
            self.assertEquals(200, reply_code)
        finally:
            f.close()

    def test_put_when_post_expected(self):
        # set expectations
        self.server.expect(method="POST", url="address/\d+/inhabitant", data='<inhabitant name="Chris"/>').and_return(
            reply_code=204)

        # try a different method
        f, reply_code = self._make_request("http://localhost:8998/address/45/inhabitant", method="PUT",
                                           payload='<inhabitant name="Chris"/>')

        # Validate the response
        self.assertEquals("Method not allowed", f.msg)
        self.assertEquals(405, reply_code)
        self.assertTrue(f.read().startswith("Method PUT not allowed."))

        # And we have an unmet expectation which needs to mention the POST that didn't happen
        try:
            self.server.stop()
        except Exception as e:
            self.assertTrue(str(e).find("POST") > 0, str(e))

    def test_unexpected_get(self):
        f, reply_code = self._make_request("http://localhost:8998/address/45/inhabitant", method="GET")
        self.assertEquals(404, reply_code)
        self.server.stop()

    def test_repeated_get(self):
        self.server.expect(method="GET", url="counter$").and_return(content="1")
        self.server.expect(method="GET", url="counter$").and_return(content="2")
        self.server.expect(method="GET", url="counter$").and_return(content="3")

        for i in range(1, 4):
            f, reply_code = self._make_request("http://localhost:8998/counter", method="GET")
            self.assertEquals(200, reply_code)
            self.assertEquals(str(i), f.read())

    def test_extra_get(self):
        self.server.expect(method="GET", url="counter$").and_return(content="1")
        f, reply_code = self._make_request("http://localhost:8998/counter", method="GET")
        self.assertEquals(200, reply_code)
        self.assertEquals("1", f.read())

        f, reply_code = self._make_request("http://localhost:8998/counter", method="GET")
        self.assertEquals(400, reply_code)
        self.assertEquals("Expectations exhausted",f.msg)
        self.assertTrue(f.read().startswith("Expectations at this URL have already been satisfied.\n"))


class FTPTest(TestCase):
    def setUp(self):
        self.random_port = 0
        self.server = FTPStubServer(self.random_port)
        self.server.run()
        self.port = self.server.server.server_address[1]

    def tearDown(self):
        self.server.stop()

    def test_put_test_file(self):
        self.assertFalse(self.server.files("foo.txt"))
        ftp = FTP()
        ftp.set_debuglevel(0)
        ftp.connect('localhost', self.port)
        ftp.login('user1', 'passwd')

        ftp.storlines('STOR foo.txt', StringIO('cant believe its not bitter'))
        ftp.quit()
        ftp.close()
        self.assertTrue(self.server.files("foo.txt"))

    def test_put_2_files_associates_the_correct_content_with_the_correct_filename(self):
        ftp = FTP()
        ftp.connect('localhost', self.port)
        ftp.set_debuglevel(0)
        ftp.login('user2','other_pass')

        ftp.storlines('STOR robot.txt', StringIO("\n".join(["file1 content" for i in range(1024)])))
        ftp.storlines('STOR monster.txt', StringIO("file2 content"))
        ftp.quit()
        ftp.close()
        self.assertEquals("\r\n".join(["file1 content" for i in range(1024)]),
                          self.server.files("robot.txt").strip())
        self.assertEquals("file2 content", self.server.files("monster.txt").strip())

    def test_retrieve_expected_file_returns_file(self):
        expected_content = 'content of my file\nis a complete mystery to me.'
        self.server.add_file('foo.txt', expected_content)
        ftp = FTP()
        ftp.set_debuglevel(2)
        ftp.connect('localhost', self.port)
        ftp.login('chris', 'tarttelin')
        directory_content = []
        ftp.retrlines('LIST', lambda x: directory_content.append(x))
        file_content = []
        ftp.retrlines('RETR foo.txt', lambda x: file_content.append(x))
        ftp.quit()
        ftp.close()
        self.assertTrue('foo.txt' in '\n'.join(directory_content))
        self.assertEquals(expected_content, '\n'.join(file_content))


class VerifyTest(TestCase):
    def setUp(self):
        self.server = StubServer(8998)

    def test_verify_checks_all_expectations(self):
        satisfied_expectation = self._MockExpectation(True)
        unsatisfied_expectation = self._MockExpectation(False)
        self.server._expectations = [
            satisfied_expectation,
            unsatisfied_expectation,
            satisfied_expectation
        ]

        self.assertRaises(Exception, self.server.verify)

    def test_verify_clears_all_expectations(self):
        satisfied_expectation = self._MockExpectation(True)
        self.server._expectations = [
            satisfied_expectation,
            satisfied_expectation,
            satisfied_expectation
        ]

        self.server.verify()

        self.assertEqual([], self.server._expectations)

    class _MockExpectation(object):
        def __init__(self, satisfied):
            self.satisfied = satisfied


if __name__=='__main__':
    unittest.main()
