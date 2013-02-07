===========================================
AVersion WSGI Version Selection Application
===========================================

AVersion is a version selection application for WSGI stacks built with
PasteDeploy.  It allows multiple versions of a given application to be
addressed via URI or content type parameter.

How AVersion Works
==================

AVersion is a composite application, similar to the Paste ``urlmap``.
It is configured with several different applications--each of which
represents a different version of the desired end application.  It can
also be configured with a special application which handles
unversioned API requests, e.g., by returning a list of the available
versions.  AVersion then selects the appropriate application to pass a
given request to, based on the URI prefix, or a version parameter on
the content type or types specified in the "Content-Type" or "Accept"
headers.  In addition, AVersion can determine the best content type
for the reply, based on the URI suffix (e.g., ".json" could map to
content type "application/json") or the "Accept" header.

Configuring AVersion
====================

The first step in configuring AVersion is to set up the section of the
Paste INI configuration file::

    [composite:main]
    use = egg:aversion#aversion

The next step is to specify the recognized versions and their
associated applications.  The default application--the one called if
no version can be determined--is specified by the ``version`` key.
The specific versions are then specified by prefixing a version
specification with ``version.``; e.g., if you call the second version
of your application "v2", you would specify ``version.v2``.  The value
of any of these keys is a Paste application.  If you have a
"vers_list" application and "api_v1" and "api_v2" as the two versions
of your API, this configuration would look like::

    version = vers_list
    version.v1 = api_v1
    version.v2 = api_v2

    [app:vers_list]
    ...

    [app:api_v1]
    ...

    [app:api_v2]
    ...

This declares the available versions, but we have not provided any
criteria to select the version to route a request to.  We will
consider a simple URI mapping first; these options are declared by
prefixing the URI prefix with ``uri.``, and the value will be one of
the declared version identifiers.  For example, let us say that the
URI "/v1" will map to the "v1" API, while "/v2" maps to the "v2" API;
the relevant configuration would then be::

    uri./v1 = v1
    uri./v2 = v2

Note that these URI prefixes will be normalized, e.g., "//v1//"
normalizes to "/v1".  Also, AVersion takes care to ensure that the
longest match will be used; if one of your URIs was "/v1.1" and the
other was "/v1", a request to "/v1.1/foo" would be routed to the
first.  Finally, the prefixes are assumed to be complete path
fragments; the configuration shown above would not route a request to
"/v2-foo" to the "v2" application, while "/v2/foo" would be so routed.

Some applications also need to allow specifying the API version
through a parameter on the content type.  For instance, if the
"Content-Type" header on a request body is set to
"application/json;version=2", we want to select the "v2" API when the
request is made against "/".  (The version determined from the URI
trumps any version determined from "Content-Type" or "Accept".)
Similarly, if the "Accept" header includes
"application/json;version=2", and the version cannot be determined
from the URI prefix or the "Content-Type" header, then we want to use
the "version" parameter on that selected content type.

To configure the recognized content types, and to set up rules that
allow selection of the correct version, declare the types as
configuration keys prefixed with ``type.``, e.g.,
``type.application/json``.  The value of this configuration key can
then declare the version with a simple text substitution, e.g.::

    type.application/json = version:"v%(version)s"

The text substitution should result in the name of the version, as
declared above.  It is also possible to alter the type, e.g., if a
given content type actually maps to another.  Consider, for instance::

    type.application/vnd.fooapp = type:"application/%(fmt)s"
        version:"v%(version)s"

In this example, the content type
"application/vnd.fooapp;fmt=json;version=2" would make a call to the
"v2" API, with the "Accept" header rewritten to select
"application/json".

Both the "type" and "version" tokens are optional in the ``type.``
configuration values.  When the "type" token is omitted, the existing
content type is used, and when the "version" token is omitted, no
version determination is made.  Do note, however, that the
"Content-Type" header of the response will likely be that appearing in
the "type" token; future work may be done to correct this.

Since the ``type.`` keys can overwrite the content types specified in
the "Accept" header, there is one more optional type of key that can
select the content type based on the URI suffix.  For instance, the
application may desire that, if the ".json" suffix is present, the
selected content type should be "application/json".  To configure
this, simply use the suffix as a configuration key; the value will be
the desired content type::

    .json = application/json

Putting this all together, a complete AVersion configuration may look
like the following::

    [composite:main]
    use = egg:aversion#aversion

    # Specify the version applications
    version = vers_list
    version.v1 = api_v1
    version.v2 = api_v2

    # Map the URI prefixes
    uri./v1 = v1
    uri./v2 = v2

    # Recognize several types
    type.application/json = version:"v%(version)s"
    type.application/xml = version:"v%(version)s"
    type.application/vnd.fooapp = type:"application/%(fmt)s"
        version:"v%(version)s"

    # Also recognize URI suffixes
    .json = application/json
    .xml = application/xml

    [app:vers_list]
    # Specify the vers_list application
    ...

    [app:api_v1]
    # Specify the v1 API application
    ...

    [app:api_v2]
    # Specify the v2 API application
    ...

Extending AVersion
==================

AVersion processes a given request first for the URI prefixes and
suffixes, then for a version specified by the "Content-Type" header on
the request body, then for a version and content type set through the
"Accept" header (for which it implements the HTTP best-match content
type algorithm).  The first content type and version found in this
processing will be used.

It is possible to extend the ``aversion.AVersion`` class to alter the
order of these processing steps, or to provide other processing
steps.  The key is to override the ``_process()`` method.  This method
takes one required argument--the request object--and one optional
"result" argument, and returns the result.  (If the result argument is
not provided, ``_process()`` allocates an instance of
``aversion.Result``.)  It calls each of ``_proc_uri()``,
``_proc_ctype_header()``, and ``_proc_accept_header()`` in turn.

Developers may also be interested in some of the available utility
functions, which are used by AVersion.  The ``quoted_split()``
function can handle splitting multi-valued headers, like the "Accept"
header, even in the face of quoted arguments possibly containing the
separator.  The ``parse_ctype()`` function takes a content type,
complete with its parameters, and returns the bare content type and a
dictionary containing those parameters.  Finally, ``best_match()``
implements the best-match algorithm for content types, and may be
useful as an example for implementing matchers for other "Accept-*"
headers.
