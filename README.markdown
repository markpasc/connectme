## Connect Me ##

Here's an experimental implementation of [OpenID Connect][] I wrote to try to decide if it's really the flagrant power grab for my web identity by big sites that it feels like.

[OpenID Connect]: http://openidconnect.com/


### What is it? ###

OpenID Connect is a proposed new version of OpenID that is based on OAuth 2. This implementation comprises two web applications:

* **`testclient.py`** is a web app that you can sign into with OpenID Connect (a "relying party").
* **`connectme.py`** is a web app that serves OpenID Connect identities.

Due to the constraints designed into OpenID Connect, the `connectme.py` server must run at the top level of a domain over SSL that is reachable from the `testclient.py` server. (I ran `testclient.py` on my local desktop, and `connectme.py` on a development server reachable from my desktop.)


### Setting it up ###

To run it, you'll need several Python modules:

* [itty][]
* [httplib2][]
* [Jinja2][]

You can `pip install -r requirements.txt` to get good versions of these.

You'll also need [Perlbal][] to run in front of the `connectme.py` server to handle decrypting the SSL. As cribbed from [LiveJournal's guide][pbssl], you can make a self-signed certificate with:

    $ openssl req -x509 -newkey rsa:1024 -keyout connectme-key.pem -out connectme-cert.pem -days 365 -nodes

[itty]: http://pypi.python.org/pypi/itty
[httplib2]: http://pypi.python.org/pypi/httplib2
[Jinja2]: http://pypi.python.org/pypi/Jinja2
[Perlbal]: http://search.cpan.org/dist/Perlbal/
[pbssl]: http://www.livejournal.com/doc/server/lj.install.supplemental_sw.perlbal.html#lj.install.supplemental_sw.perlbal-complete


### Using it ###

Once both servers are running, view the `testclient.py` website in your browser. Enter the URL or domain name of the `connectme.py` website to begin logging in. (You'll then be asked to ignore the self-signedness of the `connectme.py` server's cert.) Once you're on the `connectme.py` site, enter the username with which to identify to the OpenID Connect client. You'll then be returned to the `testclient.py` web site, which will greet you with the identifier including the username you entered.


### Future work ###

As an experiment, this implementation is incomplete in several important ways:

* `testclient.py` finishes after getting the access token and identifier from the `connectme.py` server; a real implementation would make the request to the protected resource at the identifier to get all the available profile information.
* The `connectme.py` server asks you at the authorization step as whom to identify to the client; a real implementation would have accounts.
* Both the client and server only support JSON; a real implementation would probably support the other available serializations, maybe.
* The `connectme.py` server only produces bearer tokens; a real implementation would provide an access token secret when asked by the client, for use with non-`https` protected resources.

However it illustrates the basic flow of OpenID Connect.
