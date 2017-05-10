# Copyright (c) 2017 Patricio Cubillos and contributors.
# repack is open-source software under the MIT license (see LICENSE).

import sys, os
import struct
import warnings

import scipy.interpolate as sip
import scipy.constants as sc
import numpy as np

# Config Parser changed between Python2 and Python3:
if sys.version_info.major == 3:
  import configparser
else:
  import ConfigParser as configparser

from . import utils     as u
from . import constants as c


def parser(cfile):
  """
  Parse input arguments from configuration file.

  Parameters
  ----------
  cfile: String
     A configuration file.

  Returns
  -------
  files: List of strings
     List with line-transition file names.
  outfile: String
     Output file root name.
  tmin: Float
     Minimum temperature to sample.
  tmax: Float
     Maximum temperature to sample.
  dtemp: Float
     Temperature sampling rate.
  wnmin: Float
     Minimum wavenumber (cm-1) to sample.
  wnmax: Float
     Maximum wavenumber (cm-1) to sample.
  dwn: Float
     Wavenumber sampling rate (cm-1).
  sthresh: Float
     Threshold tolerance level for weak/strong lines.
  pffile: String
     Input partition-function file (for HITRAN input dbtype).
  chunksize: Integer
     Maximum size of chunks to read.
  """
  config = configparser.SafeConfigParser()
  config.read([cfile])
  section = "REPACK"
  # Input line-transition files:
  lblfiles = config.get(section, "lblfiles")
  lblfiles = lblfiles.split()
  # Database type:
  db = config.get(section, "dbtype")
  # Output file:
  outfile  = config.get(section, "outfile")
  # Partition-function file:
  pffile = None
  if config.has_option(section, "pffile"):
    pffile = config.get(section, "pffile")
  # Max chunk size (default 15 million):
  chunksize = 15000000
  if config.has_option(section, "chunksize"):
    chunksize = int(config.get(section, "chunksize"))

  # Temperature sampling:
  tmin  = config.getfloat(section, "tmin")
  tmax  = config.getfloat(section, "tmax")
  dtemp = config.getfloat(section, "dtemp")

  # Wavenumber sampling:
  wnmin = config.getfloat(section, "wnmin")
  wnmax = config.getfloat(section, "wnmax")
  dwn   = config.getfloat(section, "dwn")

  # Line-strength threshold:
  sthresh = config.getfloat(section, "sthresh")

  return lblfiles, db, outfile, tmin, tmax, dtemp, wnmin, wnmax, dwn, \
         sthresh, pffile, chunksize


def repack(files, dbtype, outfile, tmin, tmax, dtemp, wnmin, wnmax, dwn,
           sthresh, pffile=None, chunksize=15000000):
  """
  Re-pack line-transition data into lbl data for strong lines and
  continuum data for weak lines.

  Parameters
  ----------
  files: List of strings
     List with line-transition file names.
  dbtype: String
    Database type (exomol or hitran).
  outfile: String
     Output file root name.
  tmin: Float
     Minimum temperature to sample.
  tmax: Float
     Maximum temperature to sample.
  dtemp: Float
     Temperature sampling rate.
  wnmin: Float
     Minimum wavenumber (cm-1) to sample.
  wnmax: Float
     Maximum wavenumber (cm-1) to sample.
  dwn: Float
     Wavenumber sampling rate (cm-1).
  sthresh: Float
     Threshold tolerance level for weak/strong lines.
  pffile: String
     Input partition-function file (for HITRAN input dbtype).
  chunksize: Integer
     Maximum size of chunks to read.
  """

  # Temperature sampling:
  ntemp = int((tmax-tmin)/dtemp + 1)
  temperature = np.linspace(tmin, tmax, ntemp)

  # Wavenumber sampling:
  nwave = int((wnmax-wnmin)/dwn + 1)
  wnspec = np.linspace(wnmin, wnmax, nwave)
  continuum = np.zeros((nwave, ntemp), np.double)

  if dbtype not in ["hitran", "exomol"]:
    print("\n{:s}\n  Error: Invalid database, dbtype must be either hitran "
          "or exomol.\n{:s}\n".format(70*":", 70*":"))
    sys.exit(0)

  # Parse input files:
  nfiles = len(files)
  suff, mol, isot, pf, states = [], [],  [], [], []
  for i in np.arange(nfiles):
    s, m, iso, p, st = u.parse_file(files[i], dbtype)
    suff.append(s)
    mol.append(m)
    isot.append(iso)
    pf.append(p)
    states.append(st)

  if len(np.unique(mol)) > 1:
    print("\n{:s}\n  Error: All input files must correspont to the same "
          "molecule.\n{:s}\n".format(70*":", 70*":"))
    sys.exit(0)
  mol = mol[0]

  z = []  # Interpolator function for partition function per isotope
  if pffile is not None:
    # Read input partition-function file (if given):
    pftemp, partf, isotopes = u.read_pf(pffile, dbtype="pyrat")
    isotopes = list(isotopes)
    for j in np.arange(len(isotopes)):
      z.append(sip.interp1d(pftemp, partf[j], kind='slinear'))
  else:
    isotopes = list(np.unique(isot))
  niso = len(isotopes)

  # Isotopic abundance ratio and mass:
  iratio, imass = u.read_iso(mol, isotopes, dbtype)

  s = suff[:]  # Make a copy
  # File indices for each wavenumber set:
  wnset = []
  while np.size(s) != 0:
    suffix = s[np.argmin(s)]
    idx = []
    for i in np.arange(nfiles):
      if suff[i] == suffix:
        idx.append(i)
        s.remove(suffix)
    wnset.append(idx)

  iso = np.zeros(nfiles, int)
  if dbtype == "exomol":
    for i in np.arange(nfiles):
      iso[i] = isotopes.index(isot[i])
    # Read partition-function and states files:
    lblargs = []
    for j in np.arange(niso):
      i = isot.index(isotopes[j])
      # Partition function:
      if pffile is None:
        temp, part = u.read_pf(pf[i], dbtype)
        z.append(sip.interp1d(temp, part, kind='slinear'))
      # States:
      elow, degen = u.read_states(states[i])
      lblargs.append([elow, degen, i])

  elif dbtype == "hitran":
    lblargs = [[None, None, None]]  # Trust me

  # Turn isotopes from string to integer data type:
  isotopes = np.asarray(isotopes, int)

  # Set output file names:
  lbl_out  = "{:s}_{:s}_{:s}_lbl.dat".      format(mol, dbtype, outfile)
  cont_out = "{:s}_{:s}_{:s}_continuum.dat".format(mol, dbtype, outfile)
  # Output line-by-line file:
  lblf = open(lbl_out, "wb")

  # Read line-by-line files:
  for i in np.arange(len(wnset)):
    # Gather data from all files in this wavenumber range:
    lbl, istart, nlines = [], [], []
    for k in np.arange(len(wnset[i])):
      # Initialize lbl object (not reading yet):
      idx = wnset[i][k]
      j = int(iso[wnset[i][k]])
      print("Reading: '{:s}'.".format(files[idx]))
      lbl.append(u.lbl(files[idx], dbtype, *lblargs[j]))
      # Find initial value in range:
      i0 = lbl[k].bs(wnmin, 0,  lbl[k].nlines-1)
      while i0 > 0 and lbl[k].getwn(i0-1) >= wnmin:
        i0 -= 1
      # Find final value in range:
      iN = lbl[k].bs(wnmax, i0, lbl[k].nlines-1)
      while iN < lbl[k].nlines-1 and lbl[k].getwn(iN+1) <= wnmin:
        iN += 1
      istart.append(i0)
      nlines.append(iN-i0)

    # Count lines, set target chunk size:
    nchunks = int(np.sum(nlines)/chunksize) + 1
    target  = np.sum(nlines)/nchunks
    chunk   = np.zeros((len(wnset[i]), nchunks+1), int)
    # First and last are easy:
    chunk[:,      0] = istart
    chunk[:,nchunks] = chunk[:,0] + nlines
    # Easy-case split if only one file:
    if len(wnset[i]) == 1:
      chunk[0] = np.linspace(chunk[0,0], chunk[0,-1], nchunks+1)
    else:  # Complicated case:
      wnchunk = np.linspace(wnmin, wnmax, nchunks+1)
      # Intermediate boundaries:
      for n in np.arange(1, nchunks):
        zero = np.sum(chunk[:,n-1])
        wnchunk[n] = u.wnbalance(lbl, wnchunk[n-1], wnmax, target, zero)
        for k in np.arange(len(wnset[i])):
          chunk[k,n] = lbl[k].bs(wnchunk[n], chunk[k,n-1], chunk[k,nchunks])

    # Proccess chunks:
    for n in np.arange(nchunks):
      gf   = np.array([])
      Elow = np.array([])
      wn   = np.array([])
      iiso = np.array([], int)
      for k in np.arange(len(wnset[i])):
        # Read the LBL files by chunks:
        gfosc, el, wnumber, isoID = lbl[k].read(chunk[k,n:n+2])
        gf   = np.hstack([gf,   gfosc  ])
        Elow = np.hstack([Elow, el     ])
        wn   = np.hstack([wn,   wnumber])
        iiso = np.hstack([iiso, isoID  ])
      # Sort by wavelength:
      asort = np.argsort(wn)
      gf   = gf  [asort]
      Elow = Elow[asort]
      wn   = wn  [asort]
      iiso = iiso[asort]

      # Low temperature line flagging:
      Z = np.zeros(niso)
      for j in np.arange(niso):
        Z[j] = z[j](tmin)
      s = (gf*iratio[iiso]/Z[iiso] *
           np.exp(-c.C2*Elow/tmin) * (1-np.exp(-c.C2*wn/tmin)))
      # Line Doppler width:
      alphad = wn/(100*sc.c) * np.sqrt(2.0*c.kB*tmin / (imass[iiso]*c.amu))
      # Line-strength sorted in descending order:
      isort  = np.argsort(s/alphad)[::-1]
      flag = np.ones(len(iiso), bool)
      comment = ""
      if nchunks > 1:
        comment = " (chunk {}/{})".format(n+1, nchunks)
      print("  Flagging lines at {:4.0f} K{:s}:".format(tmin, comment))
      # Flag strong/weak lines:
      u.flag(flag, wn, s/alphad, isort, alphad, sthresh)
      print("  Compression rate:       {:.2f}%,  {:9,d}/{:10,d} lines.".
            format(np.sum(1-flag)*100./len(flag), np.sum(flag), len(wn)))

      # High temperature line flagging:
      for j in np.arange(niso):
        Z[j] = z[j](tmax)
      s = (gf*iratio[iiso]/Z[iiso] *
           np.exp(-c.C2*Elow/tmax) * (1-np.exp(-c.C2*wn/tmax)))
      alphad = wn/(100*sc.c) * np.sqrt(2.0*c.kB*tmax / (imass[iiso]*c.amu))
      isort  = np.argsort(s/alphad)[::-1]
      print("  Flagging lines at {:4.0f} K:".format(tmax))
      flag2 = np.ones(len(iiso), bool)
      u.flag(flag2, wn, s/alphad/np.sqrt(np.pi), isort, alphad, sthresh)
      print("  Compression rate:       {:.2f}%,  {:9,d}/{:10,d} lines.".
            format(np.sum(1-flag2)*100./len(flag2), np.sum(flag2), len(wn)))
      # Update flag:
      flag |= flag2
      print("  Total compression rate: {:.2f}%,  {:9,d}/{:10,d} lines.\n".
            format(np.sum(1-flag)*100./len(flag), np.sum(flag), len(wn)))

      # Store weak lines to continuum file as function of temp:
      for t in np.arange(ntemp):
        T = temperature[t]
        for j in np.arange(niso):
          Z[j] = z[j](temperature[t])
        # Line strength in cm molec-1
        s = (c.C3 * gf*iratio[iiso]/Z[iiso] *
               np.exp(-c.C2*Elow/T) * (1-np.exp(-c.C2*wn/T)))
        # Continuum opacity in cm-1 amagat-1 (instead of cm2 molec-1):
        u.continuum(s[~flag], wn[~flag], continuum[:,t], wnspec)
      # Store strong lines to LBL data file:
      indices = np.arange(len(wn))[flag]
      for m in indices:
        lblf.write(struct.pack("dddi", wn[m], Elow[m], gf[m],
                                       isotopes[iiso[m]]))

    for k in np.arange(len(wnset[i])):
      lbl[k].close()

  # Close LBL file:
  print("Kept a total of {:,.0f} line transitions.".
         format(lblf.tell()/struct.calcsize("dddi")))
  lblf.close()

  # Convert from cm2 molec-1 to cm-1 amagat-1:
  continuum *= c.N0
  # Save Continuum data to file:
  with open(cont_out, "w") as f:
    # Write header:
    f.write("@SPECIES\n{:s}\n\n".format(mol))
    f.write("@TEMPERATURES\n        ")
    for j in np.arange(ntemp):
        f.write(" {:10.0f}".format(temperature[j]))
    f.write("\n\n")
    # Write the data:
    f.write("# Wavenumber in cm-1, CIA coefficients in cm-1 amagat-1:\n")
    f.write("@DATA\n")
    for i in np.arange(nwave):
      f.write(" {:12.6f} ".format(wnspec[i]))
      for j in np.arange(ntemp):
        f.write(" {:10.4e}".format(continuum[i,j]))
      f.write("\n")

  print("Successfully rewriten {:s} line-transition info into:\n  '{:s}' and"
        "\n  '{:s}'.".format(dbtype, lbl_out, cont_out))

