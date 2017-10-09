RPM Spec File Notes
-------------------

The RPM spec file provided here is for Btc1 1.14.3 and builds on Fedora 25.

When porting the spec file to build for a particular distribution, there are
some important notes.

## Credits

This RPM spec file is based upon the work of Michael Hampton at
[Ringing Liberty](https://www.ringingliberty.com/bitcoin/). He has been
packaging Bitcoin for Fedora at least since 2012.
<<<<<<< HEAD
=======

Most of the differences between his packaging and this package are stylistic in
nature. The major differences:

1. He builds from a github tagged release rather than a release tarball. This
should not result in different source code.

2. He does not build BerkeleyDB but instead uses the BerkeleyDB provided by the
Linux distribution. For the distributions he packages for, they currently all
use the same version of BerkeleyDB so that difference is *probably* just
academic.

3. As of his 10.11.2 package he did not allow for building against LibreSSL,
specifying a build without the Qt GUI, or specifying which version of the Qt
libraries to use.

4. I renamed the `bitcoin` package that contains the Qt GUI to `bitcoin-core` as
that appears to be how the general population refers to it, in contrast to
`bitcoin-xt` or `bitcoin-classic`. I wanted to make sure the general population
knows what they are getting when installing the GUI package.

As far as minor differences, I generally prefer to assign the file permissions
in the `%files` portion of an RPM spec file rather than specifying the
permissions of a file during `%install` and other minor things like that
are largely just cosmetic.
>>>>>>> 3751912e8e044958d5ccea847a3f8eab0b026dc1
