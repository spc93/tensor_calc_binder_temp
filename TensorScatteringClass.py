# new version uses cctbx for cif reading instead of old cif loader

import sys, pprint
from copy import deepcopy
from numpy.linalg import inv
from numpy.random import rand
from scipy.special import factorial
import numpy as np
from numpy.linalg import det, norm
import matplotlib.pyplot as plt
#sys.path.append('/home/spc93/python/PyCifRW-3.1.2')
#sys.path.append('/media/DCF0769CF0767D18/python/PyCifRW-3.1.2')

class TensorScatteringClass():  
    '''
    Python class for resonant tensor scattering.

    To run test with supplied CIF file in ipython (sometimes need to repeat for plot): %run TensorScatteringClass
    
    

    While this currently has limited capability for magnetic systems, magnetic symmetry operators are used throughout
    If no Site keyword arg supplied then available sites will be displayed before exiting
    Useful methods:
        latt2b          compute reciprocal or real-space B matrix from lattice
        equiv_sites     compute symmetry-equivalent sites for selected site
        invert          inverts current spacegroup operators and sites
        isGroup(sg)     Returns True if sg forms a group or False and shows message if not (self.isGroup(self.sglist) should return True)
        TensorCalc      Calculate tensor properties for crystal and reflection; save tensors as attributes; print tensor information
        print_tensors() Display crystal/atomic/structure factor spherical/Cartesian tensors
        CalculateIntensityInPolarizationChannels    calculate four intensity channels vs psi
        PlotIntensityInPolarizationChannels        plot sigma or pi intensity vs azimuthal angle
        
    Useful parameters:
        lattice
        B
        sglist
        pglist
        crystalpglist
        Ts_crystal, Ts_atom, Fs (spherical tensors)
        Tc_crystal, Tc_atom, Fc (spherical tensors)
        
    '''
    
    
    def __init__(self, CIFfile=None, Site=None, spacegroup_number = None, wyckoff_letter = 'a', lattice = None, TimeEven=False, verbose = True):
        self.tensortypes = ['E1E1','E1E2','E2E2'] # supported tensor types
        self.processes = self.tensortypes+['E1E1mag','NonResMag'] # processes list includes magnetic scattering (not treated in tensor framework)
        self.Fs = None   #placeholder for spherical scattering tensor (if defined)
        self.verbose = verbose
        self.fmt='\n%28s:  '
         
        if not CIFfile == None:
            (self.symxyz, self.sitevec, self.Site, self.lattice) = self.symInfoFromCifFile(CIFfile, Site)
        elif not spacegroup_number == None:
            (self.symxyz, self.sitevec, self.Site) = self.symInfoFromSpacegroupAndWyckoff(spacegroup_number, wyckoff_letter)
        else:
            raise ValueError('=== Must specify either CIF file and site label or Spacegroup number and Wyckoff letter')
        if not lattice == None:
            self.lattice = lattice  # use lattice parameters if supplied
        elif CIFfile == None:       # if not supplied and no CIF file then use default lattice
            self.lattice = [0.5, 0.5, 0.5, 90, 90, 90]
                

        self.sglist=self.spacegroup_list_from_genpos_list(self.symxyz)
        
        if TimeEven==True:  #add time-reversal symmetry operator - doubles size of spacegroup
            __sgnew=deepcopy(self.sglist)
            for __sym in __sgnew:
                __sym[2]=-__sym[2]
            self.sglist+=__sgnew
         
        #calculate B matrix
        self.B=self.latt2b(self.lattice)
        
        self.pglist= self.site_sym(self.sglist, self.sitevec)   #point group of site
        self.crystalpglist = self.crystal_point_sym(self.sglist)
        
        if CIFfile == None:
            self.CIFfile = 'Spacegroup # %i' % spacegroup_number
            self.all_labels = ''
        else:
            self.CIFfile = CIFfile
        
        
        if self.verbose: 
            print(self.__repr__())
        

                

    def symInfoFromSpacegroupAndWyckoff(self, sg_num, wyck_letter, site = None):
        '''
        Get symxyz (general positions as strings from spacegroup and Wyckoff letter
        returns site after substituting either given x, y, z values or random numbers
        Requires CCTBX package
        '''
        import cctbx.sgtbx as sg
    
        sgi = sg.space_group_info(sg_num)
        sg = sgi.group()
        w = sgi.wyckoff_table()
        
        self.all_letters = list([w.position(i).letter() for i in range(w.size())])
        
        if wyck_letter in self.all_letters:
            opxyz = str(w.position(wyck_letter).special_op()) # generic xyz string for site
        else:
            print('=== Invalid Wyckoff letter for spacegroup. Valid letters:', self.all_letters)
            raise(ValueError)
            
        opxyz = opxyz.replace('/','./') # fix for Python 2.x int divide - not needed for Python 3
    
        if not site == None:        #use random values for x,y,z if not specified
            x, y, z = site
        else:
            x, y, z = rand(), rand(), rand()
    
        sitevec = np.array(eval(opxyz)) # numerical array for site
        sitevec = self.firstCell(sitevec) # put in first unit cell
        symxyz = [str(s.as_xyz()) for s in sg.all_ops()]    # all sg ops as xyz list
        sitestr = '%s %s' % (str(w.position(wyck_letter).multiplicity()), wyck_letter) 
    
        return (symxyz, sitevec, sitestr)


    def symInfoFromCifFile_old(self, CIFfile, Site): # old vserion using CifFile - can delete
        try:
            import CifFile
        except:
            print("=== You need to install the PyCifRW module and add it to the Python path.\n=== Use pip install PyCifRW or visit https://pypi.org/project/PyCifRW/")

        self.CIFfile = CIFfile
        self.Site = Site
        self.cif_obj = CifFile.CifFile(self.CIFfile)
        firstkey = self.cif_obj.keys()[0]; cb = self.cifblock=self.cif_obj[firstkey]
        lattice = [float(cb['_cell_length_a'].partition('(')[0]), float(cb['_cell_length_b'].partition('(')[0]), float(cb['_cell_length_c'].partition('(')[0]), float(cb['_cell_angle_alpha'].partition('(')[0]), float(cb['_cell_angle_beta'].partition('(')[0]), float(cb['_cell_angle_gamma'].partition('(')[0])]
        self.all_labels=', '.join(cb['_atom_site_label'])
        
        try:
            self.atom_index = cb['_atom_site_label'].index(Site)
        except:
            print("=== Error: site keyword string must be in the atomic site list: " + self.all_labels)
            return
        
        sitevec = np.array([float(cb['_atom_site_fract_x'][self.atom_index].split('(')[0]), float(cb['_atom_site_fract_y'][self.atom_index].split('(')[0]), float(cb['_atom_site_fract_z'][self.atom_index].split('(')[0]) ])

        try:
            symxyz=cb['_symmetry_equiv_pos_as_xyz']
        except:
            symxyz=cb['_space_group_symop_operation_xyz'] #assume this is full group, not just generators

        return (symxyz, sitevec, Site, lattice)


    def symInfoFromCifFile(self, CIFfile, Site): # new version using cctbx
        try:
            import iotbx.cif
        except:
            print("=== You need to install the cctbx module (available from conda)")

        
        self.CIFfile = CIFfile
        self.Site = Site

        cif_model = iotbx.cif.reader(file_path = CIFfile).model()
        firstkey = cif_model.keys()[0]
        cb = self.cifblock = cif_model[firstkey]   # get first block
        
        lattice = [float(cb['_cell_length_a'].partition('(')[0]), float(cb['_cell_length_b'].partition('(')[0]), float(cb['_cell_length_c'].partition('(')[0]), float(cb['_cell_angle_alpha'].partition('(')[0]), float(cb['_cell_angle_beta'].partition('(')[0]), float(cb['_cell_angle_gamma'].partition('(')[0])]
        self.all_labels = ', '.join(cb['_atom_site_label'])

        try:
            self.atom_index = list(cb['_atom_site_label']).index(Site)
        except:
            print("=== Error: site keyword string must be in the atomic site list: " + self.all_labels)
            return
        
        sitevec = np.array([float(cb['_atom_site_fract_x'][self.atom_index].split('(')[0]), float(cb['_atom_site_fract_y'][self.atom_index].split('(')[0]), float(cb['_atom_site_fract_z'][self.atom_index].split('(')[0]) ])
                
        try:
            symxyz=list(cb['_symmetry_equiv_pos_as_xyz'])
        except:
            symxyz=list(cb['_space_group_symop_operation_xyz']) #assume this is full group, not just generators

        return (symxyz, sitevec, Site, lattice)


                
    def __repr__(self):
        if self.Site==None:
            return "=== Atomic site labels: \n" + self.all_labels + "\n=== Use Site keyword to specific a site, e.g. Site = 'Fe1'"
        #self.fmt='\n%28s:  ' ########## delete
            
        return '\nCrystal properties\n' \
        + (self.fmt+'%s') % ('CIF file',self.CIFfile) \
        + (self.fmt+'%.3f %.3f %.3f %.2f %.2f %.2f') % ('Lattice',self.lattice[0], self.lattice[1], self.lattice[2], self.lattice[3], self.lattice[4], self.lattice[5]) \
        + (self.fmt+'%s')  %  ('All sites', self.all_labels)  \
        + (self.fmt+'%s')  %  ('Site selected', self.Site)  \
        + (self.fmt+'%.3f %.3f %.3f')  % ('Site vector', self.sitevec[0], self.sitevec[1], self.sitevec[2]) \
        + (self.fmt+'%i') % ('No. of spacegroup ops', len(self.sglist)) \
        + (self.fmt+'%i') % ('No. of sym ops at site', len(self.pglist)) \
        + (self.fmt+'%i') % ('No. of equiv. sites in cell', int(len(self.sglist)/len(self.pglist))) \
        + (self.fmt+'%i') % ('No. of pg ops for crystal', len(self.crystalpglist))

    def TensorCalc(self, hkl=np.array([0,0,0]), K=None, Parity=+1, Time=+1):
        '''
        hkl, hkln:   hkl values for reflection and azimuthal reference
        '''
        self.K = K
        self.hkl = hkl
        self.Parity = Parity
        self.Time = Time
        
        txtoe=['Even', 'Odd', 'Either', 'Either'];
        
        outstr = '\nTensor properties\n'\
            + (self.fmt+'%s') % ('Required parity', self.msg(self.Parity, txtoe)) \
            + (self.fmt+'%s') % ('Required time sym.', self.msg(self.Time, txtoe)) \
        
        outstr += self.SF_symmetry(self.sitevec, self.hkl, self.sglist)
        outstr += (self.fmt+'%r') % ('Glide or screw', self.glide_screw)
        
        #populate tensor with random complex numbers that satisfy the requirements for a Hermitian tensor
        self.Ts=list(np.zeros(2*self.K+1))
        self.Ts[self.K]=rand()
        for Qp in range(1,self.K+1):
            #Qn=-Qp; 
            rndr=rand(); rndi=rand();
            self.Ts[K-Qp]=rndr+rndi*1.J;
            self.Ts[K+Qp]=(-1)**Qp*(rndr-rndi*1.J);
        
        self.Tc1=self.spherical_to_cart_tensor(self.Ts)   #convert to cartesian tensor of same rank
        self.Tc_atom=self.apply_sym(self.Tc1, self.pglist, self.B, P=Parity, T=Time);  #apply site symmetry using site point group ops and B matrix
        self.Tc_crystal=self.apply_sym(self.Tc1, self.crystalpglist, self.B, P=Parity, T=Time);  #apply site symmetry using crystal point group ops and B matrix
        self.Fc=self.calc_SF(self.Tc1, self.sitevec, self.hkl, self.sglist, self.B, P=Parity, T=Time);   #calc SF Crt tensor using crystal space group and B matrix

        amp = self.Fc.flatten()[np.abs(self.Fc).flatten().argmax()] # find a large value in the tensor
        self.tensor_scattering_phase = np.arctan2(np.imag(amp), np.real(amp)) # calculate its phase (assume same phase for all elements)
        self.Fc_before_normalization = self.Fc * 1.0    #store un-normalized tensor Fc for reference  
        self.Fc=self.norm_array(self.Fc)    #normalize tensor

        self.Ts_atom=self.norm_array(self.cart_to_spherical_tensor(self.Tc_atom));    #atomic spherical tensor
        self.Ts_crystal=self.norm_array(self.cart_to_spherical_tensor(self.Tc_crystal));    #crystal spherical tensor
        self.Fs=self.norm_array(self.cart_to_spherical_tensor(self.Fc));    #SF spherical tensor

        if self.verbose:
            print(outstr)
        return

    def calcXrayVectors(self, lam, psi, hkl, hkln):
        '''
        calculate relevant Cartesian vector in sample reference frame
        return(h, q0, q1, esig, e0pi, e1pi)
        '''
        self.theta = theta = np.arcsin(lam*norm(np.dot(self.B, hkl))/2)

        h=x=np.array([1,0,0])
        q0=np.array([-np.sin(theta), np.cos(theta),0])
        q1=np.array([np.sin(theta),np.cos(theta),0])
        esig=z=np.array([0,0,1])
        epi0=np.array([np.cos(theta),np.sin(theta),0])
        epi1=np.array([np.cos(theta),-np.sin(theta),0])
        y=np.array([0,1,0])
         
        Uctheta=self.theta_to_cartesian(hkl,hkln,psi,self.B)
        
        h_c=x_c=np.dot(Uctheta, h)
        q0_c=np.dot(Uctheta,q0)
        q1_c=np.dot(Uctheta,q1)
        esig_c=z_c=np.dot(Uctheta,esig)
        e0pi_c=np.dot(Uctheta,epi0)
        e1pi_c=np.dot(Uctheta,epi1)
        y_c=np.dot(Uctheta,y)
        
        return(h_c, q0_c, q1_c, esig_c, e0pi_c, e1pi_c) 


    def Xtensor(self, process, rank, time, parity, e0, e1, q0, q1):
        '''
        Calculates resonant scattering tensor as per Lovesey
        This version is a dump of the output of a Mathematica implementation (hence messy!)
        The Sympy version of this calculation carries out the same tensor calculation 
        '''
        [e0x, e0y, e0z]=e0
        [e1x, e1y, e1z]=e1
        [q0x, q0y, q0z]=q0
        [q1x, q1y, q1z]=q1

        Complex=self.Complex    #make it easier to convert Mathematica Fortran output
        Sqrt=self.Sqrt

        if process=='E1E1' and rank==2 and parity==1:
            X2=np.array([
            ((e0x-Complex(0,1)*e0y)*(e1x-Complex(0,1)*e1y))/2.,
            (e0z*(e1x-Complex(0,1)*e1y)+(e0x-Complex(0,1)*e0y)*e1z)/2.,
            -((e0x*e1x+e0y*e1y-2*e0z*e1z)/Sqrt(6)),
            (-(e0z*e1x)-Complex(0,1)*e0z*e1y-e0x*e1z-Complex(0,1)*e0y*e1z)/2.,
            ((e0x+Complex(0,1)*e0y)*(e1x+Complex(0,1)*e1y))/2.
            ])
            return X2
        if process=='E1E2' and rank==3 and parity==-1:
            #E1E2 rank 3
            n3t=np.array([
            ((e0x-Complex(0,1)*e0y)*(Complex(0,1)*e1x+e1y)*
            (q0x-Complex(0,1)*q0y))/(2.*Sqrt(10)),
            (e0z*(Complex(0,1)*e1x+e1y)*(q0x-Complex(0,1)*q0y)+
            (Complex(0,1)*e0x+e0y)*
            (e1z*(q0x-Complex(0,1)*q0y)+(e1x-Complex(0,1)*e1y)*q0z))/
            (2.*Sqrt(15)),(Complex(0,0.1)*
            (-((e0x-Complex(0,1)*e0y)*(e1x+Complex(0,1)*e1y)*
            (q0x-Complex(0,1)*q0y))+
            4*e1z*(e0z*(q0x-Complex(0,1)*q0y)+
            (e0x-Complex(0,1)*e0y)*q0z)-
            2*(e1x-Complex(0,1)*e1y)*(e0x*q0x+e0y*q0y-2*e0z*q0z)))/Sqrt(6),
            (Complex(0,-0.2)*(e0x*e1z*q0x+e0y*e1z*q0y+e0x*e1x*q0z+
            e0y*e1y*q0z+e0z*(e1x*q0x+e1y*q0y-2*e1z*q0z)))/Sqrt(2),
            (Complex(0,0.1)*((e0x+Complex(0,1)*e0y)*(e1x-Complex(0,1)*e1y)*
            (q0x+Complex(0,1)*q0y)-
            4*e1z*(e0z*(q0x+Complex(0,1)*q0y)+
            (e0x+Complex(0,1)*e0y)*q0z)+
            2*(e1x+Complex(0,1)*e1y)*(e0x*q0x+e0y*q0y-2*e0z*q0z)))/Sqrt(6),
            (Complex(0,0.5)*(e0z*(e1x+Complex(0,1)*e1y)*(q0x+Complex(0,1)*q0y)+
            (e0x+Complex(0,1)*e0y)*
            (e1z*(q0x+Complex(0,1)*q0y)+(e1x+Complex(0,1)*e1y)*q0z)))/
            Sqrt(15),((e0x+Complex(0,1)*e0y)*(Complex(0,-1)*e1x+e1y)*
            (q0x+Complex(0,1)*q0y))/(2.*Sqrt(10))
            ])
            n3=np.array([
            ((e0x-Complex(0,1)*e0y)*(Complex(0,1)*e1x+e1y)*
            (q1x-Complex(0,1)*q1y))/(2.*Sqrt(10)),
            (e0z*(Complex(0,1)*e1x+e1y)*(q1x-Complex(0,1)*q1y)+
            (Complex(0,1)*e0x+e0y)*
            (e1z*(q1x-Complex(0,1)*q1y)+(e1x-Complex(0,1)*e1y)*q1z))/
            (2.*Sqrt(15)),(Complex(0,0.1)*
            (-((e0x+Complex(0,1)*e0y)*(e1x-Complex(0,1)*e1y)*
            (q1x-Complex(0,1)*q1y))+
            4*e0z*(e1z*(q1x-Complex(0,1)*q1y)+
            (e1x-Complex(0,1)*e1y)*q1z)-
            2*(e0x-Complex(0,1)*e0y)*(e1x*q1x+e1y*q1y-2*e1z*q1z)))/Sqrt(6),
            (Complex(0,-0.2)*(e0x*e1z*q1x+e0y*e1z*q1y+e0x*e1x*q1z+
            e0y*e1y*q1z+e0z*(e1x*q1x+e1y*q1y-2*e1z*q1z)))/Sqrt(2),
            (Complex(0,0.1)*((e0x-Complex(0,1)*e0y)*(e1x+Complex(0,1)*e1y)*
            (q1x+Complex(0,1)*q1y)-
            4*e0z*(e1z*(q1x+Complex(0,1)*q1y)+
            (e1x+Complex(0,1)*e1y)*q1z)+
            2*(e0x+Complex(0,1)*e0y)*(e1x*q1x+e1y*q1y-2*e1z*q1z)))/Sqrt(6),
            (Complex(0,0.5)*(e0z*(e1x+Complex(0,1)*e1y)*(q1x+Complex(0,1)*q1y)+
            (e0x+Complex(0,1)*e0y)*
            (e1z*(q1x+Complex(0,1)*q1y)+(e1x+Complex(0,1)*e1y)*q1z)))/
            Sqrt(15),((e0x+Complex(0,1)*e0y)*(Complex(0,-1)*e1x+e1y)*
            (q1x+Complex(0,1)*q1y))/(2.*Sqrt(10))
            ])
            if time==1:
                return n3t-n3
            elif time==-1:
                return  n3t+n3
        if process=='E1E2' and rank==2 and parity==-1:
            #E1E2 rank 2
            n2t=np.array([(e0z*(Complex(0,1)*e1x+e1y)*(q0x-Complex(0,1)*q0y)+(e0x-Complex(0,1)*e0y)*(Complex(0,-2)*e1z*q0x-2*e1z*q0y+Complex(0,1)*e1x*q0z+e1y*q0z))/(2.*Sqrt(30)),(e0z*(Complex(0,-1)*e1z*q0x-e1z*q0y+Complex(0,2)*e1x*q0z+2*e1y*q0z)+e0y*(Complex(0,1)*e1y*q0x+e1x*(q0x-Complex(0,2)*q0y)-e1z*q0z)+e0x*(-2*e1y*q0x+e1x*q0y+Complex(0,1)*e1y*q0y-Complex(0,1)*e1z*q0z))/(2.*Sqrt(30)),(-(e0z*e1y*q0x)+e0z*e1x*q0y+e0y*e1x*q0z-e0x*e1y*q0z)/(2.*Sqrt(5)),(e0z*(Complex(0,-1)*e1z*q0x+e1z*q0y+Complex(0,2)*e1x*q0z-2*e1y*q0z)+e0x*(2*e1y*q0x-e1x*q0y+Complex(0,1)*e1y*q0y-Complex(0,1)*e1z*q0z)+e0y*(Complex(0,1)*e1y*q0x-e1x*(q0x+Complex(0,2)*q0y)+e1z*q0z))/(2.*Sqrt(30)),(e0z*(Complex(0,-1)*e1x+e1y)*(q0x+Complex(0,1)*q0y)+(e0x+Complex(0,1)*e0y)*(Complex(0,2)*e1z*q0x-2*e1z*q0y-Complex(0,1)*e1x*q0z+e1y*q0z))/(2.*Sqrt(30))])
            n2=np.array([(Complex(0,-2)*e0z*(e1x-Complex(0,1)*e1y)*(q1x-Complex(0,1)*q1y)+(Complex(0,1)*e0x+e0y)*(e1z*(q1x-Complex(0,1)*q1y)+(e1x-Complex(0,1)*e1y)*q1z))/(2.*Sqrt(30)),(Complex(0,-1)*e0z*(e1z*q1x-Complex(0,1)*e1z*q1y+e1x*q1z-Complex(0,1)*e1y*q1z)+e0x*(e1y*q1x+e1x*q1y-Complex(0,2)*e1y*q1y+Complex(0,2)*e1z*q1z)+e0y*(-2*e1x*q1x+Complex(0,1)*e1y*q1x+Complex(0,1)*e1x*q1y+2*e1z*q1z))/(2.*Sqrt(30)),(-(e0y*(e1z*q1x+e1x*q1z))+e0x*(e1z*q1y+e1y*q1z))/(2.*Sqrt(5)),(e0z*(Complex(0,-1)*e1z*q1x+e1z*q1y-Complex(0,1)*e1x*q1z+e1y*q1z)+e0y*(2*e1x*q1x+Complex(0,1)*e1y*q1x+Complex(0,1)*e1x*q1y-2*e1z*q1z)-e0x*(e1y*q1x+e1x*q1y+Complex(0,2)*e1y*q1y-Complex(0,2)*e1z*q1z))/(2.*Sqrt(30)),(Complex(0,2)*e0z*(e1x+Complex(0,1)*e1y)*(q1x+Complex(0,1)*q1y)+(Complex(0,-1)*e0x+e0y)*(e1z*(q1x+Complex(0,1)*q1y)+(e1x+Complex(0,1)*e1y)*q1z))/(2.*Sqrt(30))])
            if time==1:
                return n2t-n2
            elif time==-1:
                return  n2t+n2
        if process=='E1E2' and rank==1 and parity==-1:
            #E1E2 rank 1
            print("xxxxx E1E2 rank 1 not tested")
            n1t=np.array([(Complex(0,0.1)*(-3*(e0x-Complex(0,1)*e0y)*(e1x+Complex(0,1)*e1y)*(q0x-Complex(0,1)*q0y)-3*e1z*(e0z*(q0x-Complex(0,1)*q0y)+(e0x-Complex(0,1)*e0y)*q0z)-(e1x-Complex(0,1)*e1y)*(e0x*q0x+e0y*q0y-2*e0z*q0z)))/Sqrt(6),(Complex(0,-0.1)*(-2*e0x*e1z*q0x-2*e0y*e1z*q0y+3*e0x*e1x*q0z+3*e0y*e1y*q0z+e0z*(3*e1x*q0x+3*e1y*q0y+4*e1z*q0z)))/Sqrt(3),(Complex(0,0.1)*(3*(e0x+Complex(0,1)*e0y)*(e1x-Complex(0,1)*e1y)*(q0x+Complex(0,1)*q0y)+3*e1z*(e0z*(q0x+Complex(0,1)*q0y)+(e0x+Complex(0,1)*e0y)*q0z)+(e1x+Complex(0,1)*e1y)*(e0x*q0x+e0y*q0y-2*e0z*q0z)))/Sqrt(6)])
            n1=np.array([(Complex(0,0.1)*(-3*(e0x+Complex(0,1)*e0y)*(e1x-Complex(0,1)*e1y)*(q1x-Complex(0,1)*q1y)-3*e0z*(e1z*(q1x-Complex(0,1)*q1y)+(e1x-Complex(0,1)*e1y)*q1z)-(e0x-Complex(0,1)*e0y)*(e1x*q1x+e1y*q1y-2*e1z*q1z)))/Sqrt(6),(Complex(0,0.1)*(-3*(e0x*e1z*q1x+e0y*e1z*q1y+e0x*e1x*q1z+e0y*e1y*q1z)+2*e0z*(e1x*q1x+e1y*q1y-2*e1z*q1z)))/Sqrt(3),(Complex(0,0.1)*(3*(e0x-Complex(0,1)*e0y)*(e1x+Complex(0,1)*e1y)*(q1x+Complex(0,1)*q1y)+3*e0z*(e1z*(q1x+Complex(0,1)*q1y)+(e1x+Complex(0,1)*e1y)*q1z)+(e0x+Complex(0,1)*e0y)*(e1x*q1x+e1y*q1y-2*e1z*q1z)))/Sqrt(6)])
            if time==1:
                return n1t-n1
            elif time==-1:
                return  n1t+n1
    
        if process=='E2E2' and rank==0 and parity==1 and time==1:
            XQQ0=np.array([(e0y*(3*e1y*q0x*q1x-2*e1x*q0y*q1x+3*e1x*q0x*q1y+4*e1y*q0y*q1y+
    3*e1z*q0z*q1y-2*e1z*q0y*q1z+3*e1y*q0z*q1z)+
    e0z*(3*e1z*q0x*q1x-2*e1x*q0z*q1x+3*e1z*q0y*q1y-2*e1y*q0z*q1y+
    3*e1x*q0x*q1z+3*e1y*q0y*q1z+4*e1z*q0z*q1z)+
    e0x*(3*e1y*q0y*q1x+3*e1z*q0z*q1x-2*e1y*q0x*q1y-2*e1z*q0x*q1z+
    e1x*(4*q0x*q1x+3*q0y*q1y+3*q0z*q1z)))/(6.*Sqrt(5))])
            return XQQ0
        if process=='E2E2' and rank==1 and parity==1 and time==-1:
            XQQ1=np.array([(e0x*(-2*e1x*q0z*q1x+Complex(0,1)*e1y*q0z*q1x+
    Complex(0,1)*e1x*q0z*q1y+2*e1x*q0x*q1z-
    Complex(0,1)*e1x*q0y*q1z+e1y*q0y*q1z+
    e1z*(2*q0x*q1x-Complex(0,1)*q0y*q1x+q0y*q1y+2*q0z*q1z))-
    Complex(0,1)*e0y*(Complex(0,-1)*e1y*q0z*q1x-
    Complex(0,1)*e1x*q0z*q1y-2*e1y*q0z*q1y+e1x*q0x*q1z+
    Complex(0,1)*e1y*q0x*q1z+2*e1y*q0y*q1z+
    e1z*(q0x*q1x+Complex(0,1)*q0x*q1y+2*q0y*q1y+2*q0z*q1z))-
    e0z*(e1x*(2*q0x*q1x-Complex(0,1)*q0x*q1y+q0y*q1y+2*q0z*q1z)-
    Complex(0,1)*(2*e1z*(Complex(0,1)*q0z*q1x+q0z*q1y-
    Complex(0,1)*q0x*q1z-q0y*q1z)+
    e1y*(q0x*q1x+Complex(0,1)*q0y*q1x+2*q0y*q1y+2*q0z*q1z))))/
    (4.*Sqrt(5)),(Complex(0,0.5)*
    (e0z*(e1z*q0y*q1x-e1z*q0x*q1y-e1y*q0x*q1z+e1x*q0y*q1z)-
    e0x*(2*e1y*q0x*q1x-2*e1x*q0y*q1x+2*e1x*q0x*q1y+
    2*e1y*q0y*q1y+e1z*q0z*q1y+e1y*q0z*q1z)+
    e0y*(2*e1y*q0y*q1x+e1z*q0z*q1x-2*e1y*q0x*q1y+
    e1x*(2*q0x*q1x+2*q0y*q1y+q0z*q1z))))/Sqrt(10),
    (e0x*(e1x*(-2*q0z*q1x-Complex(0,1)*q0z*q1y+2*q0x*q1z+
    Complex(0,1)*q0y*q1z)+e1y*(Complex(0,-1)*q0z*q1x+q0y*q1z)+
    e1z*(2*q0x*q1x+Complex(0,1)*q0y*q1x+q0y*q1y+2*q0z*q1z))-
    e0z*(2*e1z*(q0z*(q1x+Complex(0,1)*q1y)-
    (q0x+Complex(0,1)*q0y)*q1z)+
    e1y*(Complex(0,1)*q0x*q1x+q0y*q1x+Complex(0,2)*q0y*q1y+
    Complex(0,2)*q0z*q1z)+
    e1x*(2*q0x*q1x+Complex(0,1)*q0x*q1y+q0y*q1y+2*q0z*q1z))+
    e0y*(-(e1x*q0z*q1y)+Complex(0,1)*e1x*q0x*q1z+
    e1y*(-(q0z*(q1x+Complex(0,2)*q1y))+
    (q0x+Complex(0,2)*q0y)*q1z)+
    e1z*(q0x*(Complex(0,1)*q1x+q1y)+
    Complex(0,2)*(q0y*q1y+q0z*q1z))))/(4.*Sqrt(5))])
            return XQQ1
        if process=='E2E2' and rank==2 and parity==1 and time==1:
            XQQ2=np.array([(e0z*(-3*e1z*(q0x-Complex(0,1)*q0y)*(q1x-Complex(0,1)*q1y)+
    (e1x-Complex(0,1)*e1y)*
    (4*q0z*q1x-Complex(0,4)*q0z*q1y-3*q0x*q1z+
    Complex(0,3)*q0y*q1z))+
    e0y*(e1z*(Complex(0,3)*q0z*q1x+3*q0z*q1y-Complex(0,4)*q0x*q1z-
    4*q0y*q1z)+Complex(0,1)*e1x*
    (2*q0x*q1x+2*q0y*q1y+3*q0z*q1z)+
    e1y*(Complex(0,2)*q0y*q1x+Complex(0,2)*q0x*q1y+4*q0y*q1y+
    3*q0z*q1z))+e0x*(e1x*
    (-4*q0x*q1x+Complex(0,2)*q0y*q1x+Complex(0,2)*q0x*q1y-
    3*q0z*q1z)+Complex(0,1)*
    (e1z*(Complex(0,3)*q0z*q1x+3*q0z*q1y-Complex(0,4)*q0x*q1z-
    4*q0y*q1z)+e1y*(2*q0x*q1x+2*q0y*q1y+3*q0z*q1z))))/
    (4.*Sqrt(21)),(e0y*(e1y*(-3*q0z*q1x+Complex(0,2)*q0z*q1y-
    3*q0x*q1z+Complex(0,2)*q0y*q1z)+
    e1x*(Complex(0,-4)*q0z*q1x-3*q0z*q1y+Complex(0,3)*q0x*q1z+
    4*q0y*q1z)+e1z*(Complex(0,3)*q0x*q1x+4*q0y*q1x-
    3*q0x*q1y+Complex(0,2)*q0y*q1y+Complex(0,2)*q0z*q1z))-
    e0x*(e1x*(2*q0z*q1x-Complex(0,3)*q0z*q1y+2*q0x*q1z-
    Complex(0,3)*q0y*q1z)+
    e1y*(Complex(0,-3)*q0z*q1x-4*q0z*q1y+Complex(0,4)*q0x*q1z+
    3*q0y*q1z)+e1z*(Complex(0,-3)*q0y*q1x+
    2*q0x*(q1x+Complex(0,2)*q1y)+3*q0y*q1y+2*q0z*q1z))+
    e0z*(-2*e1z*(q0z*q1x-Complex(0,1)*q0z*q1y+q0x*q1z-
    Complex(0,1)*q0y*q1z)+
    e1y*(Complex(0,3)*q0x*q1x-3*q0y*q1x+4*q0x*q1y+
    Complex(0,2)*q0y*q1y+Complex(0,2)*q0z*q1z)-
    e1x*(2*q0x*q1x+Complex(0,4)*q0y*q1x-Complex(0,3)*q0x*q1y+
    3*q0y*q1y+2*q0z*q1z)))/(4.*Sqrt(21)),
    (e0y*(6*e1y*q0x*q1x-8*e1x*q0y*q1x+6*e1x*q0x*q1y+4*e1y*q0y*q1y-
    3*e1z*q0z*q1y+4*e1z*q0y*q1z-3*e1y*q0z*q1z)-
    e0z*(3*e1z*q0x*q1x-4*e1x*q0z*q1x+3*e1z*q0y*q1y-4*e1y*q0z*q1y+
    3*e1x*q0x*q1z+3*e1y*q0y*q1z+8*e1z*q0z*q1z)+
    e0x*(6*e1y*q0y*q1x-3*e1z*q0z*q1x-8*e1y*q0x*q1y+4*e1z*q0x*q1z+
    e1x*(4*q0x*q1x+6*q0y*q1y-3*q0z*q1z)))/(6.*Sqrt(14)),
    (e0y*(e1x*(Complex(0,-4)*q0z*q1x+3*q0z*q1y+Complex(0,3)*q0x*q1z-
    4*q0y*q1z)+e1y*(3*q0z*q1x+Complex(0,2)*q0z*q1y+
    3*q0x*q1z+Complex(0,2)*q0y*q1z)+
    e1z*(-4*q0y*q1x+Complex(0,2)*q0y*q1y+
    3*q0x*(Complex(0,1)*q1x+q1y)+Complex(0,2)*q0z*q1z))+
    e0x*(e1x*(2*q0z*q1x+Complex(0,3)*q0z*q1y+2*q0x*q1z+
    Complex(0,3)*q0y*q1z)+
    e1y*(Complex(0,3)*q0z*q1x-4*q0z*q1y-Complex(0,4)*q0x*q1z+
    3*q0y*q1z)+e1z*(Complex(0,3)*q0y*q1x+
    2*q0x*(q1x-Complex(0,2)*q1y)+3*q0y*q1y+2*q0z*q1z))+
    e0z*(2*e1z*(q0z*q1x+Complex(0,1)*q0z*q1y+q0x*q1z+
    Complex(0,1)*q0y*q1z)+
    e1y*(Complex(0,3)*q0x*q1x+3*q0y*q1x-4*q0x*q1y+
    Complex(0,2)*q0y*q1y+Complex(0,2)*q0z*q1z)+
    e1x*(2*q0x*q1x-Complex(0,4)*q0y*q1x+Complex(0,3)*q0x*q1y+
    3*q0y*q1y+2*q0z*q1z)))/(4.*Sqrt(21)),
    (Complex(0,-1)*(e0z*(3*e1z*(Complex(0,-1)*q0x+q0y)*
    (q1x+Complex(0,1)*q1y)+
    (e1x+Complex(0,1)*e1y)*
    (Complex(0,4)*q0z*q1x-4*q0z*q1y-Complex(0,3)*q0x*q1z+
    3*q0y*q1z))+e0y*
    (e1z*(3*q0z*(q1x+Complex(0,1)*q1y)-
    4*(q0x+Complex(0,1)*q0y)*q1z)+
    e1y*(2*q0y*(q1x+Complex(0,2)*q1y)+2*q0x*q1y+
    Complex(0,3)*q0z*q1z)+
    e1x*(2*q0x*q1x+2*q0y*q1y+3*q0z*q1z)))-
    e0x*(e1x*(4*q0x*q1x+Complex(0,2)*q0y*q1x+Complex(0,2)*q0x*q1y+
    3*q0z*q1z)+Complex(0,1)*
    (e1z*(Complex(0,-3)*q0z*q1x+3*q0z*q1y+Complex(0,4)*q0x*q1z-
    4*q0y*q1z)+e1y*(2*q0x*q1x+2*q0y*q1y+3*q0z*q1z))))/
    (4.*Sqrt(21))])
            return XQQ2
        if process=='E2E2' and rank==3 and parity==1 and time==-1:
            XQQ3=np.array([(e0z*(e1x-Complex(0,1)*e1y)*(q0x-Complex(0,1)*q0y)*
    (q1x-Complex(0,1)*q1y)-
    (e0x-Complex(0,1)*e0y)*e1z*(q0x-Complex(0,1)*q0y)*
    (q1x-Complex(0,1)*q1y)+
    (e0x-Complex(0,1)*e0y)*(e1x-Complex(0,1)*e1y)*q0z*
    (q1x-Complex(0,1)*q1y)-
    (e0x-Complex(0,1)*e0y)*(e1x-Complex(0,1)*e1y)*
    (q0x-Complex(0,1)*q0y)*q1z)/(4.*Sqrt(2)),
    (Complex(0,0.25)*(Complex(0,-2)*e0z*(e1x-Complex(0,1)*e1y)*q0z*
    (q1x-Complex(0,1)*q1y)+
    e0y*(e1y*q0y*q1x-e1y*q0x*q1y+
    e1x*(-(q0x*q1x)+Complex(0,2)*q0y*q1x+q0y*q1y)+
    2*e1z*q0x*q1z-Complex(0,2)*e1z*q0y*q1z)+
    e0x*(e1y*q0x*q1x-e1x*q0y*q1x+e1x*q0x*q1y-
    Complex(0,2)*e1y*q0x*q1y-e1y*q0y*q1y+
    Complex(0,2)*e1z*q0x*q1z+2*e1z*q0y*q1z)))/Sqrt(3),
    (Complex(0,-1)*e0y*(e1x*(5*q0z*q1x-Complex(0,3)*q0z*q1y+
    3*q0x*q1z-Complex(0,5)*q0y*q1z)+
    e1y*(Complex(0,-3)*q0z*q1x-q0z*q1y+Complex(0,3)*q0x*q1z+
    q0y*q1z)+e1z*(Complex(0,-5)*q0y*q1x+
    3*q0x*(q1x+Complex(0,1)*q1y)+q0y*q1y-4*q0z*q1z))+
    e0x*(e1x*(-(q0z*q1x)+Complex(0,3)*q0z*q1y+q0x*q1z-
    Complex(0,3)*q0y*q1z)+
    e1y*(Complex(0,3)*q0z*q1x+5*q0z*q1y+Complex(0,5)*q0x*q1z+
    3*q0y*q1z)+e1z*(Complex(0,-3)*q0y*q1x+
    q0x*(q1x+Complex(0,5)*q1y)+3*q0y*q1y-4*q0z*q1z))+
    e0z*(4*e1z*(q0z*q1x-Complex(0,1)*q0z*q1y-q0x*q1z+
    Complex(0,1)*q0y*q1z)-
    e1x*(Complex(0,5)*q0y*q1x+q0x*(q1x-Complex(0,3)*q1y)+
    3*q0y*q1y-4*q0z*q1z)+
    e1y*(Complex(0,3)*q0x*q1x-3*q0y*q1x+5*q0x*q1y+
    Complex(0,1)*q0y*q1y-Complex(0,4)*q0z*q1z)))/(4.*Sqrt(30)),
    (Complex(0,0.5)*(2*e0z*(-(e1z*q0y*q1x)+e1z*q0x*q1y+e1y*q0x*q1z-
    e1x*q0y*q1z)+e0y*(e1y*q0y*q1x-2*e1z*q0z*q1x-e1y*q0x*q1y+
    e1x*(q0x*q1x+q0y*q1y-2*q0z*q1z))+
    e0x*(e1x*q0y*q1x-e1x*q0x*q1y+2*e1z*q0z*q1y-
    e1y*(q0x*q1x+q0y*q1y-2*q0z*q1z))))/Sqrt(10),
    (Complex(0,1)*e0y*(e1x*(5*q0z*q1x+Complex(0,3)*q0z*q1y+3*q0x*q1z+
    Complex(0,5)*q0y*q1z)+
    e1y*(Complex(0,3)*q0z*q1x-q0z*q1y-Complex(0,3)*q0x*q1z+
    q0y*q1z)+e1z*(Complex(0,5)*q0y*q1x+
    3*q0x*(q1x-Complex(0,1)*q1y)+q0y*q1y-4*q0z*q1z))+
    e0x*(e1x*(-(q0z*(q1x+Complex(0,3)*q1y))+
    (q0x+Complex(0,3)*q0y)*q1z)+
    e1y*(Complex(0,-3)*q0z*q1x+5*q0z*q1y-Complex(0,5)*q0x*q1z+
    3*q0y*q1z)+e1z*(Complex(0,3)*q0y*q1x+
    q0x*(q1x-Complex(0,5)*q1y)+3*q0y*q1y-4*q0z*q1z))-
    e0z*(4*e1z*(-(q0z*(q1x+Complex(0,1)*q1y))+
    (q0x+Complex(0,1)*q0y)*q1z)+
    e1x*(Complex(0,-5)*q0y*q1x+q0x*(q1x+Complex(0,3)*q1y)+
    3*q0y*q1y-4*q0z*q1z)+
    e1y*(Complex(0,3)*q0x*q1x+3*q0y*q1x-5*q0x*q1y+
    Complex(0,1)*q0y*q1y-Complex(0,4)*q0z*q1z)))/(4.*Sqrt(30)),
    (Complex(0,0.25)*(Complex(0,2)*e0z*(e1x+Complex(0,1)*e1y)*q0z*
    (q1x+Complex(0,1)*q1y)+
    e0y*(e1y*q0y*q1x-e1y*q0x*q1y+
    e1x*(-(q0x*q1x)-Complex(0,2)*q0y*q1x+q0y*q1y)+
    2*e1z*q0x*q1z+Complex(0,2)*e1z*q0y*q1z)+
    e0x*(e1y*q0x*q1x-e1x*q0y*q1x+e1x*q0x*q1y+
    Complex(0,2)*e1y*q0x*q1y-e1y*q0y*q1y-
    Complex(0,2)*e1z*q0x*q1z+2*e1z*q0y*q1z)))/Sqrt(3),
    (e0z*(e1x+Complex(0,1)*e1y)*(q0x+Complex(0,1)*q0y)*
    (q1x+Complex(0,1)*q1y)-
    (e0x+Complex(0,1)*e0y)*(e1z*(q0x+Complex(0,1)*q0y)*
    (q1x+Complex(0,1)*q1y)-
    (e1x+Complex(0,1)*e1y)*
    (q0z*(q1x+Complex(0,1)*q1y)-(q0x+Complex(0,1)*q0y)*q1z)))/
    (4.*Sqrt(2))])
            return XQQ3
        if process=='E2E2' and rank==4 and parity==1 and time==1:
            #nedit replace \n \r and ' ' with nothing.
            #List((( -> array([(( and add square bracket after first round, also at end
            XQQ4=np.array([((e0x-Complex(0,1)*e0y)*(e1x-Complex(0,1)*e1y)*
    (q0x-Complex(0,1)*q0y)*(q1x-Complex(0,1)*q1y))/4.,
    (e0z*(e1x-Complex(0,1)*e1y)*(q0x-Complex(0,1)*q0y)*
    (q1x-Complex(0,1)*q1y)+
    (e0x-Complex(0,1)*e0y)*e1z*(q0x-Complex(0,1)*q0y)*
    (q1x-Complex(0,1)*q1y)+
    (e0x-Complex(0,1)*e0y)*(e1x-Complex(0,1)*e1y)*q0z*
    (q1x-Complex(0,1)*q1y)+
    (e0x-Complex(0,1)*e0y)*(e1x-Complex(0,1)*e1y)*
    (q0x-Complex(0,1)*q0y)*q1z)/(4.*Sqrt(2)),
    (e0x*(e1x*(-2*q0x*q1x+Complex(0,1)*q0y*q1x+Complex(0,1)*q0x*q1y+
    2*q0z*q1z)+Complex(0,1)*
    (Complex(0,-2)*e1z*(q0z*q1x-Complex(0,1)*q0z*q1y+q0x*q1z-
    Complex(0,1)*q0y*q1z)+e1y*(q0x*q1x+q0y*q1y-2*q0z*q1z))\
    )+Complex(0,1)*(Complex(0,-2)*e0z*
    (e1z*(q0x-Complex(0,1)*q0y)*(q1x-Complex(0,1)*q1y)+
    (e1x-Complex(0,1)*e1y)*
    (q0z*(q1x-Complex(0,1)*q1y)+(q0x-Complex(0,1)*q0y)*q1z))\
    +e0y*(-2*e1z*(q0z*q1x-Complex(0,1)*q0z*q1y+q0x*q1z-
    Complex(0,1)*q0y*q1z)+
    e1x*(q0x*q1x+q0y*q1y-2*q0z*q1z)+
    e1y*(q0y*q1x+q0x*q1y-Complex(0,2)*q0y*q1y+
    Complex(0,2)*q0z*q1z))))/(4.*Sqrt(7)),
    (-(e0x*(e1x*(3*q0z*q1x-Complex(0,1)*q0z*q1y+3*q0x*q1z-
    Complex(0,1)*q0y*q1z)+
    e1y*(Complex(0,-1)*q0z*q1x+q0z*q1y-Complex(0,1)*q0x*q1z+
    q0y*q1z)+e1z*(3*q0x*q1x-Complex(0,1)*q0y*q1x-
    Complex(0,1)*q0x*q1y+q0y*q1y-4*q0z*q1z)))-
    e0z*(-4*e1z*(q0z*q1x-Complex(0,1)*q0z*q1y+q0x*q1z-
    Complex(0,1)*q0y*q1z)+
    e1x*(3*q0x*q1x-Complex(0,1)*q0y*q1x-Complex(0,1)*q0x*q1y+
    q0y*q1y-4*q0z*q1z)+
    e1y*(Complex(0,-1)*q0x*q1x+q0y*q1x+q0x*q1y-
    Complex(0,3)*q0y*q1y+Complex(0,4)*q0z*q1z))-
    e0y*(e1y*(q0z*q1x-Complex(0,3)*q0z*q1y+q0x*q1z-
    Complex(0,3)*q0y*q1z)+
    e1x*(Complex(0,-1)*q0z*q1x+q0z*q1y-Complex(0,1)*q0x*q1z+
    q0y*q1z)+e1z*(q0y*q1x-Complex(0,3)*q0y*q1y+
    q0x*(Complex(0,-1)*q1x+q1y)+Complex(0,4)*q0z*q1z)))/
    (4.*Sqrt(14)),(e0y*(e1y*q0x*q1x+e1x*q0y*q1x+e1x*q0x*q1y+
    3*e1y*q0y*q1y-4*e1z*q0z*q1y-4*e1z*q0y*q1z-4*e1y*q0z*q1z)-
    4*e0z*(e1z*q0x*q1x+e1x*q0z*q1x+e1z*q0y*q1y+e1y*q0z*q1y+
    e1x*q0x*q1z+e1y*q0y*q1z-2*e1z*q0z*q1z)+
    e0x*(e1y*q0y*q1x-4*e1z*q0z*q1x+e1y*q0x*q1y-4*e1z*q0x*q1z+
    e1x*(3*q0x*q1x+q0y*q1y-4*q0z*q1z)))/(2.*Sqrt(70)),
    (e0x*(e1x*(3*q0z*q1x+Complex(0,1)*q0z*q1y+3*q0x*q1z+
    Complex(0,1)*q0y*q1z)+
    e1y*(Complex(0,1)*q0z*q1x+q0z*q1y+Complex(0,1)*q0x*q1z+
    q0y*q1z)+e1z*(3*q0x*q1x+Complex(0,1)*q0y*q1x+
    Complex(0,1)*q0x*q1y+q0y*q1y-4*q0z*q1z))+
    e0z*(-4*e1z*(q0z*q1x+Complex(0,1)*q0z*q1y+q0x*q1z+
    Complex(0,1)*q0y*q1z)+
    e1x*(3*q0x*q1x+Complex(0,1)*q0y*q1x+Complex(0,1)*q0x*q1y+
    q0y*q1y-4*q0z*q1z)+
    e1y*(Complex(0,1)*q0x*q1x+q0y*q1x+q0x*q1y+
    Complex(0,3)*q0y*q1y-Complex(0,4)*q0z*q1z))+
    e0y*(e1y*(q0z*q1x+Complex(0,3)*q0z*q1y+q0x*q1z+
    Complex(0,3)*q0y*q1z)+
    e1x*(Complex(0,1)*q0z*q1x+q0z*q1y+Complex(0,1)*q0x*q1z+
    q0y*q1z)+e1z*(q0y*q1x+Complex(0,3)*q0y*q1y+
    q0x*(Complex(0,1)*q1x+q1y)-Complex(0,4)*q0z*q1z)))/
    (4.*Sqrt(14)),(2*e0z*(e1z*(q0x+Complex(0,1)*q0y)*
    (q1x+Complex(0,1)*q1y)+
    (e1x+Complex(0,1)*e1y)*
    (q0z*(q1x+Complex(0,1)*q1y)+(q0x+Complex(0,1)*q0y)*q1z))-
    Complex(0,1)*e0y*(-2*e1z*
    (q0z*q1x+Complex(0,1)*q0z*q1y+q0x*q1z+
    Complex(0,1)*q0y*q1z)+e1x*(q0x*q1x+q0y*q1y-2*q0z*q1z)+
    e1y*(q0y*q1x+q0x*q1y+Complex(0,2)*q0y*q1y-
    Complex(0,2)*q0z*q1z))+
    e0x*(-(e1x*(2*q0x*q1x+Complex(0,1)*q0y*q1x+
    Complex(0,1)*q0x*q1y-2*q0z*q1z))-
    Complex(0,1)*(Complex(0,2)*e1z*
    (q0z*q1x+Complex(0,1)*q0z*q1y+q0x*q1z+
    Complex(0,1)*q0y*q1z)+e1y*(q0x*q1x+q0y*q1y-2*q0z*q1z)))\
    )/(4.*Sqrt(7)),(-(e0z*(e1x+Complex(0,1)*e1y)*(q0x+Complex(0,1)*q0y)*
    (q1x+Complex(0,1)*q1y))-
    (e0x+Complex(0,1)*e0y)*
    (e1z*(q0x+Complex(0,1)*q0y)*(q1x+Complex(0,1)*q1y)+
    (e1x+Complex(0,1)*e1y)*
    (q0z*(q1x+Complex(0,1)*q1y)+(q0x+Complex(0,1)*q0y)*q1z)))/
    (4.*Sqrt(2)),((e0x+Complex(0,1)*e0y)*(e1x+Complex(0,1)*e1y)*
    (q0x+Complex(0,1)*q0y)*(q1x+Complex(0,1)*q1y))/4.])
            return XQQ4
        else:
            raise ValueError('Unknown tensor type')

    def Complex(self, a, b):          #allow FortranForm Mathematica output with only minor mods need to delete spaces, List( ... )->array([...])
        return a+b*1j
    
    def Sqrt(self, a):
        return np.sqrt(a)


    def TensorScatteringMatrix(self, mpol, Fs, time, parity, esig_c, e0pi_c, e1pi_c, q0_c,  q1_c):
        '''
        Calculate 2x2 scattering amplitude matrix for tensor scattering
        '''

        K=(len(Fs)-1)/2 #get rank K from tensor size

        X_ss=self.Xtensor(mpol, K, time, parity, esig_c, esig_c,  q0_c,  q1_c)
        X_sp=self.Xtensor(mpol, K, time, parity, esig_c, e1pi_c,  q0_c,  q1_c)
        X_ps=self.Xtensor(mpol, K, time, parity, e0pi_c, esig_c,  q0_c,  q1_c)
        X_pp=self.Xtensor(mpol, K, time, parity, e0pi_c, e1pi_c,  q0_c,  q1_c)
        
        f_ss=self.scalar_contract(X_ss, Fs)
        f_sp=self.scalar_contract(X_sp, Fs)
        f_ps=self.scalar_contract(X_ps, Fs)
        f_pp=self.scalar_contract(X_pp, Fs)
        
        
        self.G=np.array([[f_ss,  f_ps], [f_sp,  f_pp]])    #scattering matrix
        return self.G

    def NonResonantMagneticScatteringMatrix(self, sk, lk, esig_c, e0pi_c, e1pi_c, q0_c,  q1_c):
        '''
        Calculate 2x2 scattering amplitude matrix for non-resonant magnetic scattering
        spin and orbital components (complex) for reflection are sk, lk 
        BB and AA are B (spin) and A (orbit) coupling vectors from SWL, Blume etc
        '''
        e0=esig_c; e1=esig_c;
        BB=np.cross(e1,e0)+np.cross(q1_c,e1)*np.dot(q1_c,e0)-np.cross(q0_c,e0)*np.dot(q0_c,e1)-np.cross(np.cross(q1_c,e1),np.cross(q0_c,e0))
        AA=2*(1-np.dot(q0_c,q1_c))*np.cross(e1,e0)-np.cross(q0_c,e0)*np.dot(q0_c,e1)+np.cross(q1_c,e1)*np.dot(q1_c,e0)
        f_ss=1j*(np.dot(sk,BB)+np.dot(lk,AA)); 
 
        e0=esig_c; e1=e1pi_c;
        BB=np.cross(e1,e0)+np.cross(q1_c,e1)*np.dot(q1_c,e0)-np.cross(q0_c,e0)*np.dot(q0_c,e1)-np.cross(np.cross(q1_c,e1),np.cross(q0_c,e0))
        AA=2*(1-np.dot(q0_c,q1_c))*np.cross(e1,e0)-np.cross(q0_c,e0)*np.dot(q0_c,e1)+np.cross(q1_c,e1)*np.dot(q1_c,e0)
        f_sp=1j*(np.dot(sk,BB)+np.dot(lk,AA));
        
        e0=e0pi_c; e1=esig_c;
        BB=np.cross(e1,e0)+np.cross(q1_c,e1)*np.dot(q1_c,e0)-np.cross(q0_c,e0)*np.dot(q0_c,e1)-np.cross(np.cross(q1_c,e1),np.cross(q0_c,e0))
        AA=2*(1-np.dot(q0_c,q1_c))*np.cross(e1,e0)-np.cross(q0_c,e0)*np.dot(q0_c,e1)+np.cross(q1_c,e1)*np.dot(q1_c,e0)
        f_ps=1j*(np.dot(sk,BB)+np.dot(lk,AA));
        
        e0=e0pi_c; e1=e1pi_c;
        BB=np.cross(e1,e0)+np.cross(q1_c,e1)*np.dot(q1_c,e0)-np.cross(q0_c,e0)*np.dot(q0_c,e1)-np.cross(np.cross(q1_c,e1),np.cross(q0_c,e0))
        AA=2*(1-np.dot(q0_c,q1_c))*np.cross(e1,e0)-np.cross(q0_c,e0)*np.dot(q0_c,e1)+np.cross(q1_c,e1)*np.dot(q1_c,e0)
        f_pp=1j*(np.dot(sk,BB)+np.dot(lk,AA)); 
        
        
        self.G=np.array([[f_ss,  f_ps], [f_sp,  f_pp]])    #scattering matrix
        return self.G



    def E1E1ResonantMagneticScatteringMatrix(self, mk, esig_c, e0pi_c, e1pi_c, q0_c,  q1_c):
        '''
        Calculate 2x2 scattering amplitude matrix for E1E1 resonant magnetic scattering
        '''
        e0=esig_c; e1=esig_c;
        E1E1=np.cross(e1,e0)
        f_ss=1j*(np.dot(mk,E1E1));
 
        e0=esig_c; e1=e1pi_c;
        E1E1=np.cross(e1,e0)
        f_sp=1j*(np.dot(mk,E1E1));

        e0=e0pi_c; e1=esig_c;
        E1E1=np.cross(e1,e0)
        f_ps=1j*(np.dot(mk,E1E1));

        e0=e0pi_c; e1=e1pi_c;
        E1E1=np.cross(e1,e0)
        f_pp=1j*(np.dot(mk,E1E1));
        
        self.G=np.array([[f_ss,  f_ps], [f_sp,  f_pp]])    #scattering matrix
        return self.G

#     def CalculateIntensityInPolarizationChannels(self, process, lam, hkl, hkln, psideg, K=None, Time=None, Parity=None, mk=None, lk=None, sk=None):
#         '''
#         Calculate intensity in four linear polarization channels
#         psi can be a scalar or array/list
#         '''
# 
#         tensortypes=['E1E1','E1E2','E2E2']
#         processes=tensortypes+['E1E1mag','NonResMag']
#         assert process in processes, '=== First argument (process) should be in ' + str(processes)
# 
#         assert process not in tensortypes or (K != None and Time != None and Parity != None), '=== Need keywords K, Time, Parity for tensor processes' 
#         assert process != 'E1E1mag' or mk is not None, '=== Need keyword mk for E1E1 resonant magnetic scattering'
#         assert process != 'NonResMag' or (sk is not None and lk is not None), '=== Need keywords sk, lk (arrays) for non-resonant magnetic scattering'
#         
#         if process in tensortypes:
#             self.TensorCalc(K=K, hkl=hkl, Parity=Parity, Time=Time)
#         
#         try:
#             psi=[float(psideg)*np.pi/180]
#         except:
#             psi=np.array(psideg*np.pi/180)
# 
#         Iss, Isp,Ips, Ipp = [], [], [],[]
#         for psival in psi:
#             
#             (h, q0, q1, esig, e0pi, e1pi) = self.calcXrayVectors(lam, psival, hkl, hkln)
# 
#             if process in tensortypes:
#                 self.Xtensor(process, K, Time, Parity, esig, e1pi, q0, q1)
#                 G=self.TensorScatteringMatrix(process, self.Fs, Time, Parity, esig, e0pi, e1pi, q0,  q1)
# 
#             elif process == 'E1E1mag':
#                 G=self.E1E1ResonantMagneticScatteringMatrix(mk, esig, e0pi, e1pi, q0,  q1)
#                 
#             elif process == 'NonResMag':
#                 G=self.NonResonantMagneticScatteringMatrix(sk, lk, esig, e0pi, e1pi, q0,  q1)
#                     
#             else:
#                 raise ValueError("== Don't know what to do with process type %s: " % process)
#         
#             Iss+=[abs(G[0,0])**2]; Isp+=[abs(G[1,0])**2]; Ips+=[abs(G[0,1])**2]; Ipp+=[abs(G[1,1])**2];
#         if len(Iss)>1:
#             return (np.array(Iss), np.array(Isp), np.array(Ips), np.array(Ipp))
#         else:
#             return (Iss[0], Isp[0], Ips[0], Ipp[0])


    def CalculateAmplitudeInPolarizationChannels(self, process, lam, hkl, hkln, psideg, K=None, Time=None, Parity=None, mk=None, lk=None, sk=None):
        '''
        Calculate amplitude in four linear polarization channels
        psi can be a scalar or array/list
        '''

        assert process in self.processes, '=== First argument (process) should be in ' + str(self.processes)
        assert process not in self.tensortypes or (K != None and Time != None and Parity != None), '=== Need keywords K, Time, Parity for tensor processes' 
        assert process != 'E1E1mag' or mk is not None, '=== Need keyword mk for E1E1 resonant magnetic scattering'
        assert process != 'NonResMag' or (sk is not None and lk is not None), '=== Need keywords sk, lk (arrays) for non-resonant magnetic scattering'
        
        if process in self.tensortypes:
            self.TensorCalc(K=K, hkl=hkl, Parity=Parity, Time=Time)
        
        try:
            psi=[float(psideg)*np.pi/180]
        except:
            psi=np.array(psideg)*np.pi/180

        Ass, Asp, Aps, App = [], [], [],[]
        for psival in psi:
            
            G = self.CalculateScatteringMatrixG(process, lam, psival, hkl, hkln, Fs = self.Fs, K = K, Time = Time, Parity = Parity, mk = mk, sk = sk, lk = lk)

            Ass+=[G[0,0]]; Asp+=[G[1,0]]; Aps+=[G[0,1]]; App+=[G[1,1]];
        if len(Ass)>1:
            return (np.array(Ass), np.array(Asp), np.array(Aps), np.array(App))
        else:
            return (Ass[0], Asp[0], Aps[0], App[0])


    def CalculateIntensityInPolarizationChannels(self, process, lam, hkl, hkln, psideg, K=None, Time=None, Parity=None, mk=None, lk=None, sk=None):
        '''
        Calculate intensity in four linear polarization channels from amplitudes
        '''
        (Ass, Asp, Aps, App) = self.CalculateAmplitudeInPolarizationChannels(process, lam, hkl, hkln, psideg, K, Time, Parity, mk, lk, sk)
        
        return (abs(Ass)**2, abs(Asp)**2, abs(Aps)**2, abs(App)**2)
      
    ##### delete this function once the one above has been tested.
    def CalculateIntensityInPolarizationChannels_old_to_delete(self, process, lam, hkl, hkln, psideg, K=None, Time=None, Parity=None, mk=None, lk=None, sk=None):
        '''
        Calculate intensity in four linear polarization channels
        psi can be a scalar or array/list
        '''

        assert process in self.processes, '=== First argument (process) should be in ' + str(self.processes)
        assert process not in self.tensortypes or (K != None and Time != None and Parity != None), '=== Need keywords K, Time, Parity for tensor processes' 
        assert process != 'E1E1mag' or mk is not None, '=== Need keyword mk for E1E1 resonant magnetic scattering'
        assert process != 'NonResMag' or (sk is not None and lk is not None), '=== Need keywords sk, lk (arrays) for non-resonant magnetic scattering'
        
        if process in self.tensortypes:
            self.TensorCalc(K=K, hkl=hkl, Parity=Parity, Time=Time)
        
        try:
            psi=[float(psideg)*np.pi/180]
        except:
            psi=np.array(psideg)*np.pi/180

        Iss, Isp,Ips, Ipp = [], [], [],[]
        for psival in psi:
            
            G = self.CalculateScatteringMatrixG(process, lam, psival, hkl, hkln, Fs = self.Fs, K = K, Time = Time, Parity = Parity, mk = mk, sk = sk, lk = lk)

            Iss+=[abs(G[0,0])**2]; Isp+=[abs(G[1,0])**2]; Ips+=[abs(G[0,1])**2]; Ipp+=[abs(G[1,1])**2];
        if len(Iss)>1:
            return (np.array(Iss), np.array(Isp), np.array(Ips), np.array(Ipp))
        else:
            return (Iss[0], Isp[0], Ips[0], Ipp[0])
         
        
    def CalculateIntensityFromPolarizationAnalyser(self, process, lam, hkl, hkln, psideg, pol_eta_deg, pol_th_deg = 45, stokesvec_swl = [0, 0, 1], K = None, Time = None, Parity = None, mk = None, lk = None, sk = None):
        '''
        Calculate intensity from polarization analyser vs pol_eta (analyser rotation)
        pol_eta_deg can be a scalar or array/list
        pol_th_deg is polarizer theta angle (deg) (default 45)
        stokesvec_swl is Stokes as per SWL papers (P3 = horizontal linear, default [0 ,0, 1])
        '''       
        
        assert process in self.processes+['Scalar'], '=== First argument (process) should be in ' + str(self.processes+['Scalar'])
        assert process not in self.tensortypes or (K != None and Time != None and Parity != None), '=== Need keywords K, Time, Parity for tensor processes' 
        assert process != 'E1E1mag' or mk is not None, '=== Need keyword mk for E1E1 resonant magnetic scattering'
        assert process != 'NonResMag' or (sk is not None and lk is not None), '=== Need keywords sk, lk (arrays) for non-resonant magnetic scattering'
        
        if process in self.tensortypes:
            self.TensorCalc(K=K, hkl=hkl, Parity=Parity, Time=Time)

        
        try:
            pol_eta = [float(pol_eta_deg) * np.pi/180]
        except:
            pol_eta = np.array(pol_eta_deg) * np.pi/180
        
        pol_theta = pol_th_deg * np.pi/180
        
        if process=='Scalar':  #special case - scalar scattering not considered in the rest of the class
            self.calcXrayVectors(lam, 0, hkl, hkln) # needed to calculate theta
            G = np.array([[1, 0], [0, np.cos(2*self.theta)]])
        else:
            G = self.CalculateScatteringMatrixG(process, lam, psideg*np.pi/180, hkl, hkln, Fs = self.Fs, K = K, Time = Time, Parity = Parity, mk = mk, sk = sk, lk = lk)
        
        [P1, P2, P3] = stokesvec_swl
        mu = 1./2*np.array([[1.+P3, P1-1.J*P2], [ P1+1.J*P2, 1.-P3]])
            
        I_pol=[]
        for eta in pol_eta:
            A = np.array([[np.cos(eta), np.sin(eta)], [-np.cos(2*pol_theta)*np.sin(eta), np.cos(2*pol_theta)*np.cos(eta) ]])
            I_pol += [np.dot(A, np.dot(G, np.dot(mu,np.dot(np.conjugate(G.T), np.conjugate(A.T))))).trace()]
            
        if len(I_pol)>1:
            return np.array(I_pol)
        else:
            return I_pol[0]

    def CalculateScatteringMatrixG(self, process, lam, psival, hkl, hkln, Fs = None, K=None, Time = None, Parity = None, mk = None, sk = None, lk = None):
        '''
        Calculate G for specified scattering process; require lam, psival, hkl, hkln
        Fs (structure factor spherical tensor), Time & Parity symmetry, mk, sk, lk are required for specific processes only
        2 x 2 G matrix defined in SWL papers
        '''
       
        (h, q0, q1, esig, e0pi, e1pi) = self.calcXrayVectors(lam, psival, hkl, hkln)
        
        (h, q0, q1, esig, e0pi, e1pi) = self.calcXrayVectors(lam, psival, hkl, hkln)

        if process in self.tensortypes:
            assert Fs is not None and K is not None
            self.Xtensor(process, K, Time, Parity, esig, e1pi, q0, q1)
            G=self.TensorScatteringMatrix(process, Fs, Time, Parity, esig, e0pi, e1pi, q0,  q1)

        elif process == 'E1E1mag':
            G=self.E1E1ResonantMagneticScatteringMatrix(mk, esig, e0pi, e1pi, q0,  q1)
                
        elif process == 'NonResMag':
            G=self.NonResonantMagneticScatteringMatrix(sk, lk, esig, e0pi, e1pi, q0,  q1)
                    
        else:
            raise ValueError("== Don't know what to do with process type %s: " % process)
        
        return G

    def PlotIntensityInPolarizationChannels(self, process, lam, hkl, hkln, psideg=None, K=None, Time=None, Parity=None, mk=None, lk=None, sk=None , sigmapi=None, savefile=None, plot_amplitudes=False):
        '''
        Plot azimuthal dependence of sigma or pi intensity and save figure if savefile keyword string (fine name root) given
        If plot_amplitudes = True is given as keyword argument then amplitued are plotted instead
        Note: when plot_amplitudes is selected the varaibles Iss, Isp etc are still used but they are now amplitudes and not intensities
        '''
        
        assert sigmapi in ('sigma', 'pi'), "=== sigmapi keyword must be 'sigma' or 'pi'"

        if psideg == None:
            psideg = np.array(range(361))

        if plot_amplitudes:
            ylabeltxt = 'Amplitudes (aribtrary units)'
            Iss, Isp, Ips, Ipp = self.CalculateAmplitudeInPolarizationChannels(process, lam, hkl, hkln, psideg=psideg, K=K, Time=Time, Parity=Parity, mk=mk, lk=lk, sk=sk)
        else:
            ylabeltxt = 'Intensity (aribtrary units)'        
            Iss, Isp, Ips, Ipp = self.CalculateIntensityInPolarizationChannels(process, lam, hkl, hkln, psideg=psideg, K=K, Time=Time, Parity=Parity, mk=mk, lk=lk, sk=sk)

        #sig-sig, sig-pi, sig-total
        titlestr = process+' hkl=[%.1f, %.1f, %.1f]   $\psi_0$=[%.1f, %.1f, %.1f]' % (tuple(hkl)+tuple(hkln)) 

        if sigmapi == 'sigma':
            Ixs, Ixp, Itot, polchar = Iss, Isp, Iss + Isp, '\sigma'
        elif sigmapi == 'pi':
            Ixs, Ixp, Itot, polchar = Ips, Ipp, Ips + Ipp, '\pi'

        plt.figure(); 
        if not plot_amplitudes: # total not useful for amplitudes
            plt.plot(psideg, Itot, 'k',label='$\sigma$ Total',linewidth=2.0);
        plt.plot(psideg, Ixs, 'r',label='$'+polchar+'\sigma$',linewidth=2.0);
        plt.plot(psideg, Ixp, 'b',label='$'+polchar+'\pi$',linewidth=2.0); 
        plt.legend(loc='best'); plt.ylabel(ylabeltxt); plt.axis('tight'); plt.xlabel('$\psi$ (degrees)'); plt.title(titlestr); plt.grid(1)
        if max(abs(Itot)) < 1e-20:
            plt.ylim([0,1])

        plt.show()
        if savefile != None:
            plt.savefig(('%s '+sigmapi+'.pdf') % savefile)

    def PlotIntensityVsPolarizationAnalyserRotation(self, process, lam, hkl, hkln, psideg, pol_eta_deg, pol_th_deg = 45, stokesvec_swl = [0, 0, 1], K = None, Time = None, Parity = None, mk = None, lk = None, sk = None, savefile=None):
        '''
        Plot intensity vs PA rotation and save figure if savefile keyword string (fine name root) given
        '''

        I_pol = self.CalculateIntensityFromPolarizationAnalyser(process, lam, hkl, hkln, psideg, pol_eta_deg, pol_th_deg = pol_th_deg, stokesvec_swl = stokesvec_swl, K = K, Time = Time, Parity = Parity, mk = mk, lk = lk, sk = sk)

        titlestr = process+' hkl=[%.1f, %.1f, %.1f]   $\psi_0$=[%.1f, %.1f, %.1f]' % (tuple(hkl)+tuple(hkln)) 

        plt.figure(); 
        plt.plot(pol_eta_deg, I_pol, label='Polarization\nanalyser\nintensity',linewidth=2.0);
        
        plt.legend(loc='best'); plt.ylabel('Intensity (aribtrary units)'); plt.axis('tight'); plt.xlabel('$\eta$ (degrees)'); plt.title(titlestr); plt.grid(1)
        if max(abs(I_pol)) < 1e-20:
            plt.ylim([0,1])
        plt.show()
        if savefile != None:
            plt.savefig('%s '+etascan+'.pdf' % savefile)


    def theta_to_cartesian(self, hkl, hkln, psi, B):
        '''
        Unitary matrix for transformation from theta to cartesian coordinate system
        '''
        Rx=np.array([
        [1, 0, 0],
        [0, np.cos(psi), np.sin(psi)],
        [0, -np.sin(psi), np.cos(psi)]
        ])
        
        xp=np.dot(B, hkl)/norm(np.dot(B, hkl))
        cp=np.cross(np.dot(B, hkl),np.dot(B, hkln));
        zp=cp/norm(cp)
        yp=np.cross(zp, xp);
        Ucpsi=np.array([xp, yp, zp]).T;
        Uctheta=np.dot(Ucpsi, Rx)
        
        return Uctheta

    def scalar_contract(self, X, T):
        if len(X)!=len(T):
            raise ValueError("Can't form scalar contraction of tensors with different rank")
        K=int(len(X)/2)
        scalar=0
        for kk in range(len(X)):
            q=kk-K
            scalar+=(-1)**q * X[2*K-kk] * T[kk]
        return scalar

    def print_tensors(self):
        np.set_printoptions(precision=3, suppress=True)
        print('\nTensor components\n' +
            self.fmt % 'Crystal (spherical)' + str(self.Ts_crystal) +
            self.fmt % 'Atom (spherical)' + str(self.Ts_atom) +
            self.fmt % 'Struct. factor (spherical)' + str(self.Fs) +
            self.fmt % 'Scattering phase (rad)' +  '%.2f' % self.tensor_scattering_phase +
            '\n\nCrystal (Cartesian):\n\n' + str(self.Tc_crystal) +
            '\n\nAtom (Cartesian):\n\n' + str(self.Tc_atom) +
            '\n\nStruct. factor (Cartesian):\n\n' + str(self.Fc) + '\n')
        
#    def print_tensors(self):
#        np.set_printoptions(precision=3, suppress=True)
#        print('\nTensor components\n',\
#            self.fmt % 'Crystal (spherical)', self.Ts_crystal,\
#            self.fmt % 'Atom (spherical)', self.Ts_atom,\
#            self.fmt % 'Struct. factor (spherical)', self.Fs,\
#            '\n\nCrystal (Cartesian):\n\n', self.Tc_crystal,\
#            '\n\nAtom (Cartesian):\n\n', self.Tc_atom,\
#            '\n\nStruct. factor (Cartesian):\n\n', self.Fc, '\n')     

    
    def cart_to_spherical_tensor(self, Tc):
        K=len(Tc.shape); #Cartesian tensor rank
        Cconj=self.StoneSphericalToCartConversionCoefs(K)
        Ts=np.zeros(2*K+1, dtype=complex)
        for kk in range(-K, K+1):
            Ts[kk+K]=np.sum(Cconj[kk+K]*Tc)
        return Ts
    
    
    def apply_sym(self, Tensor, symop_list, Bmat=np.array([[1, 0, 0],[0,1,0],[0,0,1]]), P=None, T=+1):
        #apply point sym ops in symop_list to tensor of rank K
        #Optional Bmat is used to transform arrays to Cartesian from crystal basis
        #Default time (T) sym +1; no default for parity (P)
        Tnew=Tensor*0.0
        for sym in symop_list:
            tsign=T**int((1-sym[1])/2) #sign change of time-odd tensor under time inversion
            Tnew+=self.transform_cart(Tensor, self.crystal_to_cart_operator(sym[0], Bmat),P)*tsign
        return Tnew

    def norm_array(self, Array, Minval=0.001):
        #Normalise array by largest abs value if >Minval (avoids trying to renormalise zero array)
        greatest=0.0
        flatarray=Array.flat
        for i in range(len(flatarray)):
            if abs(flatarray[i])>abs(greatest):
                greatest=flatarray[i]
        if abs(greatest)>Minval:
            newarray=Array/greatest
        else:
            newarray=Array
        return newarray

    def calc_SF(self, Tensor, R, hkl, spacegroup_list, Bmat=np.array([[1, 0, 0],[0,1,0],[0,0,1]]), P=None, T=+1):
        #calc structure factor tensor for symop_list to tensot T of rank K at position R hkl=Q
        #Optional Bmat is used to transform arrays to Cartesian from crystal basis
        Tnew=Tensor*0.0
        for sym in spacegroup_list:
            mat=sym[0]
            vec=sym[1]
            time=sym[2]
            tsign=T**int((1-time)/2) #sign change of time-odd tensor under time inversion
            newR=np.dot(mat, R)+vec
            phase=np.exp(np.pi*2.j * np.dot(hkl, newR))
            newbit=self.transform_cart(Tensor, self.crystal_to_cart_operator(mat, Bmat),P)*phase*tsign
            Tnew=Tnew+newbit
        return Tnew


    def transform_cart(self, T, S, P=0):
        #transform Cart tensor rank K using symmetry operator S
        #If optional parameter P (parity) is given then a correction is made to account for the otherwise incorrect
        #tranformation of Cartesian tensors derived from spherical pseudotensors (see Mittelwihr paper)
        d=3
        k=len(T.shape); #rank of T
        if P==0:
            Sfac=1
        elif P==1 or P==-1:
            Sfac=det(S)**int((3+P*(-1)**k)/2)
        else:
            raise ValueError('Parity should be +1 (even), -1 (odd) or 0 (ignored)')
            
        ##### delete next two lines - diagnostics only
        if Sfac==-1 and self.verbose:
            print("===Applying sign change for pseudotensor transormation")
        
        tnew=T*0.0;
        if k==0:
            tnew=T
        elif k==1:
            for i in range(d):
                for ii in range(d):
                    tnew[i]+=S[i, ii]*T[ii]
        elif k==2:
            for i in range(d):
                for ii in range(d):
                    for j in range(d):
                        for jj in range(d):
                            tnew[i, j]+=S[i, ii]*S[j, jj]*T[ii, jj]
        elif k==3:
            for i in range(d):
                for ii in range(d):
                    for j in range(d):
                        for jj in range(d):
                            for k in range(d):
                                for kk in range(d):
                                    tnew[i, j, k]+=S[i, ii]*S[j, jj]*S[k, kk]*T[ii, jj, kk]
        elif k==4:
            for i in range(d):
                for ii in range(d):
                    for j in range(d):
                        for jj in range(d):
                            for k in range(d):
                                for kk in range(d):
                                    for l in range(d):
                                        for ll in range(d):
                                            tnew[i, j, k, l]+=S[i, ii]*S[j, jj]*S[k, kk]*S[l, ll]*T[ii, jj, kk, ll]                             
        elif k==5:
            for i in range(d):
                for ii in range(d):
                    for j in range(d):
                        for jj in range(d):
                            for k in range(d):
                                for kk in range(d):
                                    for l in range(d):
                                        for ll in range(d):
                                            for m in range(d):
                                                 for mm in range(d): 
                                                     tnew[i, j, k, l, m]+=S[i, ii]*S[j, jj]*S[k, kk]*S[l, ll]*S[m, mm]*T[ii, jj, kk, ll, mm]                                        
        elif k==6:
            for i in range(d):
                for ii in range(d):
                    for j in range(d):
                        for jj in range(d):
                            for k in range(d):
                                for kk in range(d):
                                    for l in range(d):
                                        for ll in range(d):
                                            for m in range(d):
                                                 for mm in range(d): 
                                                     for n in range(d):
                                                         for nn in range(d): 
                                                             tnew[i, j, k, l, m, n]+=S[i, ii]*S[j, jj]*S[k, kk]*S[l, ll]*S[m, mm]*S[n, nn]*T[ii, jj, kk, ll, mm, nn]                                        
        else:
            raise ValueError('Tranformation for this tensor rank not coded: K=',k)
        return tnew*Sfac   #Apply correction factor Sfac (+/-1)

    def crystal_to_cart_operator(self, S, B):
        pass
        #transform crystal sym op to Cart sym op using B matrix
        Snew=np.dot(inv(B.T),  np.dot(S, B.T));
        return Snew
    
    def StoneSphericalToCartConversionCoefs(self, K, Calc=True, k=-1j):
        #Condon&Shortley phase convention (k=-i in Stone's paper)
        #from FortranForm (No - CForm?) First List->array, del other lists,spaces, extra bracket around first level
        #If Calc==False then use these expressions from Mathematica, else calculate them numerically
        if not Calc:
            if K==0:
                C=np.array(1.0)
            elif K==1:
                C=np.array(((Complex(0,1)/Sqrt(2),1/Sqrt(2),0),(0,0,Complex(0,1)), (Complex(0,-1)/Sqrt(2),1/Sqrt(2),0)))
            elif K==2:
                C=np.array((((-0.5,Complex(0,0.5),0),(Complex(0,0.5),0.5,0),(0,0,0)),((0,0,-0.5),(0,0,Complex(0,0.5)),(-0.5,Complex(0,0.5),0)),((1/Sqrt(6),0,0),(0,1/Sqrt(6),0),(0,0,-Sqrt(0.6666666666666666))),((0,0,0.5),(0,0,Complex(0,0.5)),(0.5,Complex(0,0.5),0)),((-0.5,Complex(0,-0.5),0),(Complex(0,-0.5),0.5,0),(0,0,0))))
            elif K==3:
                C=np.array(((((Complex(0,-0.5)/Sqrt(2),-1/(2.*Sqrt(2)),0),(-1/(2.*Sqrt(2)),Complex(0,0.5)/Sqrt(2),0),(0,0,0)),((-1/(2.*Sqrt(2)),Complex(0,0.5)/Sqrt(2),0),(Complex(0,0.5)/Sqrt(2),1/(2.*Sqrt(2)),0),(0,0,0)),((0,0,0),(0,0,0),(0,0,0))),(((0,0,Complex(0,-0.5)/Sqrt(3)),(0,0,-1/(2.*Sqrt(3))),(Complex(0,-0.5)/Sqrt(3),-1/(2.*Sqrt(3)),0)),((0,0,-1/(2.*Sqrt(3))),(0,0,Complex(0,0.5)/Sqrt(3)),(-1/(2.*Sqrt(3)),Complex(0,0.5)/Sqrt(3),0)),((Complex(0,-0.5)/Sqrt(3),-1/(2.*Sqrt(3)),0),(-1/(2.*Sqrt(3)),Complex(0,0.5)/Sqrt(3),0),(0,0,0))),(((Complex(0,0.5)*Sqrt(0.3),1/(2.*Sqrt(30)),0),(1/(2.*Sqrt(30)),Complex(0,0.5)/Sqrt(30),0),(0,0,Complex(0,-1)*Sqrt(0.13333333333333333))),((1/(2.*Sqrt(30)),Complex(0,0.5)/Sqrt(30),0),(Complex(0,0.5)/Sqrt(30),Sqrt(0.3)/2.,0),(0,0,-Sqrt(0.13333333333333333))),((0,0,Complex(0,-1)*Sqrt(0.13333333333333333)),(0,0,-Sqrt(0.13333333333333333)),(Complex(0,-1)*Sqrt(0.13333333333333333),-Sqrt(0.13333333333333333),0))),(((0,0,Complex(0,1)/Sqrt(10)),(0,0,0),(Complex(0,1)/Sqrt(10),0,0)),((0,0,0),(0,0,Complex(0,1)/Sqrt(10)),(0,Complex(0,1)/Sqrt(10),0)),((Complex(0,1)/Sqrt(10),0,0),(0,Complex(0,1)/Sqrt(10),0),(0,0,Complex(0,-1)*Sqrt(0.4)))),(((Complex(0,-0.5)*Sqrt(0.3),1/(2.*Sqrt(30)),0),(1/(2.*Sqrt(30)),Complex(0,-0.5)/Sqrt(30),0),(0,0,Complex(0,1)*Sqrt(0.13333333333333333))),((1/(2.*Sqrt(30)),Complex(0,-0.5)/Sqrt(30),0),(Complex(0,-0.5)/Sqrt(30),Sqrt(0.3)/2.,0),(0,0,-Sqrt(0.13333333333333333))),((0,0,Complex(0,1)*Sqrt(0.13333333333333333)),(0,0,-Sqrt(0.13333333333333333)),(Complex(0,1)*Sqrt(0.13333333333333333),-Sqrt(0.13333333333333333),0))),(((0,0,Complex(0,-0.5)/Sqrt(3)),(0,0,1/(2.*Sqrt(3))),(Complex(0,-0.5)/Sqrt(3),1/(2.*Sqrt(3)),0)),((0,0,1/(2.*Sqrt(3))),(0,0,Complex(0,0.5)/Sqrt(3)),(1/(2.*Sqrt(3)),Complex(0,0.5)/Sqrt(3),0)),((Complex(0,-0.5)/Sqrt(3),1/(2.*Sqrt(3)),0),(1/(2.*Sqrt(3)),Complex(0,0.5)/Sqrt(3),0),(0,0,0))),(((Complex(0,0.5)/Sqrt(2),-1/(2.*Sqrt(2)),0),(-1/(2.*Sqrt(2)),Complex(0,-0.5)/Sqrt(2),0),(0,0,0)),((-1/(2.*Sqrt(2)),Complex(0,-0.5)/Sqrt(2),0),(Complex(0,-0.5)/Sqrt(2),1/(2.*Sqrt(2)),0),(0,0,0)),((0,0,0),(0,0,0),(0,0,0)))))
            elif K==4:
                C=np.array((((((0.25,Complex(0,-0.25),0),(Complex(0,-0.25),-0.25,0),(0,0,0)),((Complex(0,-0.25),-0.25,0),(-0.25,Complex(0,0.25),0),(0,0,0)),((0,0,0),(0,0,0),(0,0,0))),(((Complex(0,-0.25),-0.25,0),(-0.25,Complex(0,0.25),0),(0,0,0)),((-0.25,Complex(0,0.25),0),(Complex(0,0.25),0.25,0),(0,0,0)),((0,0,0),(0,0,0),(0,0,0))),(((0,0,0),(0,0,0),(0,0,0)),((0,0,0),(0,0,0),(0,0,0)),((0,0,0),(0,0,0),(0,0,0)))),((((0,0,1/(4.*Sqrt(2))),(0,0,Complex(0,-0.25)/Sqrt(2)),(1/(4.*Sqrt(2)),Complex(0,-0.25)/Sqrt(2),0)),((0,0,Complex(0,-0.25)/Sqrt(2)),(0,0,-1/(4.*Sqrt(2))),(Complex(0,-0.25)/Sqrt(2),-1/(4.*Sqrt(2)),0)),((1/(4.*Sqrt(2)),Complex(0,-0.25)/Sqrt(2),0),(Complex(0,-0.25)/Sqrt(2),-1/(4.*Sqrt(2)),0),(0,0,0))),(((0,0,Complex(0,-0.25)/Sqrt(2)),(0,0,-1/(4.*Sqrt(2))),(Complex(0,-0.25)/Sqrt(2),-1/(4.*Sqrt(2)),0)),((0,0,-1/(4.*Sqrt(2))),(0,0,Complex(0,0.25)/Sqrt(2)),(-1/(4.*Sqrt(2)),Complex(0,0.25)/Sqrt(2),0)),((Complex(0,-0.25)/Sqrt(2),-1/(4.*Sqrt(2)),0),(-1/(4.*Sqrt(2)),Complex(0,0.25)/Sqrt(2),0),(0,0,0))),(((1/(4.*Sqrt(2)),Complex(0,-0.25)/Sqrt(2),0),(Complex(0,-0.25)/Sqrt(2),-1/(4.*Sqrt(2)),0),(0,0,0)),((Complex(0,-0.25)/Sqrt(2),-1/(4.*Sqrt(2)),0),(-1/(4.*Sqrt(2)),Complex(0,0.25)/Sqrt(2),0),(0,0,0)),((0,0,0),(0,0,0),(0,0,0)))),((((-1/(2.*Sqrt(7)),Complex(0,0.25)/Sqrt(7),0),(Complex(0,0.25)/Sqrt(7),0,0),(0,0,1/(2.*Sqrt(7)))),((Complex(0,0.25)/Sqrt(7),0,0),(0,Complex(0,0.25)/Sqrt(7),0),(0,0,Complex(0,-0.5)/Sqrt(7))),((0,0,1/(2.*Sqrt(7))),(0,0,Complex(0,-0.5)/Sqrt(7)),(1/(2.*Sqrt(7)),Complex(0,-0.5)/Sqrt(7),0))),(((Complex(0,0.25)/Sqrt(7),0,0),(0,Complex(0,0.25)/Sqrt(7),0),(0,0,Complex(0,-0.5)/Sqrt(7))),((0,Complex(0,0.25)/Sqrt(7),0),(Complex(0,0.25)/Sqrt(7),1/(2.*Sqrt(7)),0),(0,0,-1/(2.*Sqrt(7)))),((0,0,Complex(0,-0.5)/Sqrt(7)),(0,0,-1/(2.*Sqrt(7))),(Complex(0,-0.5)/Sqrt(7),-1/(2.*Sqrt(7)),0))),(((0,0,1/(2.*Sqrt(7))),(0,0,Complex(0,-0.5)/Sqrt(7)),(1/(2.*Sqrt(7)),Complex(0,-0.5)/Sqrt(7),0)),((0,0,Complex(0,-0.5)/Sqrt(7)),(0,0,-1/(2.*Sqrt(7))),(Complex(0,-0.5)/Sqrt(7),-1/(2.*Sqrt(7)),0)),((1/(2.*Sqrt(7)),Complex(0,-0.5)/Sqrt(7),0),(Complex(0,-0.5)/Sqrt(7),-1/(2.*Sqrt(7)),0),(0,0,0)))),((((0,0,-3/(4.*Sqrt(14))),(0,0,Complex(0,0.25)/Sqrt(14)),(-3/(4.*Sqrt(14)),Complex(0,0.25)/Sqrt(14),0)),((0,0,Complex(0,0.25)/Sqrt(14)),(0,0,-1/(4.*Sqrt(14))),(Complex(0,0.25)/Sqrt(14),-1/(4.*Sqrt(14)),0)),((-3/(4.*Sqrt(14)),Complex(0,0.25)/Sqrt(14),0),(Complex(0,0.25)/Sqrt(14),-1/(4.*Sqrt(14)),0),(0,0,1/Sqrt(14)))),(((0,0,Complex(0,0.25)/Sqrt(14)),(0,0,-1/(4.*Sqrt(14))),(Complex(0,0.25)/Sqrt(14),-1/(4.*Sqrt(14)),0)),((0,0,-1/(4.*Sqrt(14))),(0,0,Complex(0,0.75)/Sqrt(14)),(-1/(4.*Sqrt(14)),Complex(0,0.75)/Sqrt(14),0)),((Complex(0,0.25)/Sqrt(14),-1/(4.*Sqrt(14)),0),(-1/(4.*Sqrt(14)),Complex(0,0.75)/Sqrt(14),0),(0,0,Complex(0,-1)/Sqrt(14)))),(((-3/(4.*Sqrt(14)),Complex(0,0.25)/Sqrt(14),0),(Complex(0,0.25)/Sqrt(14),-1/(4.*Sqrt(14)),0),(0,0,1/Sqrt(14))),((Complex(0,0.25)/Sqrt(14),-1/(4.*Sqrt(14)),0),(-1/(4.*Sqrt(14)),Complex(0,0.75)/Sqrt(14),0),(0,0,Complex(0,-1)/Sqrt(14))),((0,0,1/Sqrt(14)),(0,0,Complex(0,-1)/Sqrt(14)),(1/Sqrt(14),Complex(0,-1)/Sqrt(14),0)))),((((3/(2.*Sqrt(70)),0,0),(0,1/(2.*Sqrt(70)),0),(0,0,-Sqrt(0.05714285714285714))),((0,1/(2.*Sqrt(70)),0),(1/(2.*Sqrt(70)),0,0),(0,0,0)),((0,0,-Sqrt(0.05714285714285714)),(0,0,0),(-Sqrt(0.05714285714285714),0,0))),(((0,1/(2.*Sqrt(70)),0),(1/(2.*Sqrt(70)),0,0),(0,0,0)),((1/(2.*Sqrt(70)),0,0),(0,3/(2.*Sqrt(70)),0),(0,0,-Sqrt(0.05714285714285714))),((0,0,0),(0,0,-Sqrt(0.05714285714285714)),(0,-Sqrt(0.05714285714285714),0))),(((0,0,-Sqrt(0.05714285714285714)),(0,0,0),(-Sqrt(0.05714285714285714),0,0)),((0,0,0),(0,0,-Sqrt(0.05714285714285714)),(0,-Sqrt(0.05714285714285714),0)),((-Sqrt(0.05714285714285714),0,0),(0,-Sqrt(0.05714285714285714),0),(0,0,2*Sqrt(0.05714285714285714))))),((((0,0,3/(4.*Sqrt(14))),(0,0,Complex(0,0.25)/Sqrt(14)),(3/(4.*Sqrt(14)),Complex(0,0.25)/Sqrt(14),0)),((0,0,Complex(0,0.25)/Sqrt(14)),(0,0,1/(4.*Sqrt(14))),(Complex(0,0.25)/Sqrt(14),1/(4.*Sqrt(14)),0)),((3/(4.*Sqrt(14)),Complex(0,0.25)/Sqrt(14),0),(Complex(0,0.25)/Sqrt(14),1/(4.*Sqrt(14)),0),(0,0,-(1/Sqrt(14))))),(((0,0,Complex(0,0.25)/Sqrt(14)),(0,0,1/(4.*Sqrt(14))),(Complex(0,0.25)/Sqrt(14),1/(4.*Sqrt(14)),0)),((0,0,1/(4.*Sqrt(14))),(0,0,Complex(0,0.75)/Sqrt(14)),(1/(4.*Sqrt(14)),Complex(0,0.75)/Sqrt(14),0)),((Complex(0,0.25)/Sqrt(14),1/(4.*Sqrt(14)),0),(1/(4.*Sqrt(14)),Complex(0,0.75)/Sqrt(14),0),(0,0,Complex(0,-1)/Sqrt(14)))),(((3/(4.*Sqrt(14)),Complex(0,0.25)/Sqrt(14),0),(Complex(0,0.25)/Sqrt(14),1/(4.*Sqrt(14)),0),(0,0,-(1/Sqrt(14)))),((Complex(0,0.25)/Sqrt(14),1/(4.*Sqrt(14)),0),(1/(4.*Sqrt(14)),Complex(0,0.75)/Sqrt(14),0),(0,0,Complex(0,-1)/Sqrt(14))),((0,0,-(1/Sqrt(14))),(0,0,Complex(0,-1)/Sqrt(14)),(-(1/Sqrt(14)),Complex(0,-1)/Sqrt(14),0)))),((((-1/(2.*Sqrt(7)),Complex(0,-0.25)/Sqrt(7),0),(Complex(0,-0.25)/Sqrt(7),0,0),(0,0,1/(2.*Sqrt(7)))),((Complex(0,-0.25)/Sqrt(7),0,0),(0,Complex(0,-0.25)/Sqrt(7),0),(0,0,Complex(0,0.5)/Sqrt(7))),((0,0,1/(2.*Sqrt(7))),(0,0,Complex(0,0.5)/Sqrt(7)),(1/(2.*Sqrt(7)),Complex(0,0.5)/Sqrt(7),0))),(((Complex(0,-0.25)/Sqrt(7),0,0),(0,Complex(0,-0.25)/Sqrt(7),0),(0,0,Complex(0,0.5)/Sqrt(7))),((0,Complex(0,-0.25)/Sqrt(7),0),(Complex(0,-0.25)/Sqrt(7),1/(2.*Sqrt(7)),0),(0,0,-1/(2.*Sqrt(7)))),((0,0,Complex(0,0.5)/Sqrt(7)),(0,0,-1/(2.*Sqrt(7))),(Complex(0,0.5)/Sqrt(7),-1/(2.*Sqrt(7)),0))),(((0,0,1/(2.*Sqrt(7))),(0,0,Complex(0,0.5)/Sqrt(7)),(1/(2.*Sqrt(7)),Complex(0,0.5)/Sqrt(7),0)),((0,0,Complex(0,0.5)/Sqrt(7)),(0,0,-1/(2.*Sqrt(7))),(Complex(0,0.5)/Sqrt(7),-1/(2.*Sqrt(7)),0)),((1/(2.*Sqrt(7)),Complex(0,0.5)/Sqrt(7),0),(Complex(0,0.5)/Sqrt(7),-1/(2.*Sqrt(7)),0),(0,0,0)))),((((0,0,-1/(4.*Sqrt(2))),(0,0,Complex(0,-0.25)/Sqrt(2)),(-1/(4.*Sqrt(2)),Complex(0,-0.25)/Sqrt(2),0)),((0,0,Complex(0,-0.25)/Sqrt(2)),(0,0,1/(4.*Sqrt(2))),(Complex(0,-0.25)/Sqrt(2),1/(4.*Sqrt(2)),0)),((-1/(4.*Sqrt(2)),Complex(0,-0.25)/Sqrt(2),0),(Complex(0,-0.25)/Sqrt(2),1/(4.*Sqrt(2)),0),(0,0,0))),(((0,0,Complex(0,-0.25)/Sqrt(2)),(0,0,1/(4.*Sqrt(2))),(Complex(0,-0.25)/Sqrt(2),1/(4.*Sqrt(2)),0)),((0,0,1/(4.*Sqrt(2))),(0,0,Complex(0,0.25)/Sqrt(2)),(1/(4.*Sqrt(2)),Complex(0,0.25)/Sqrt(2),0)),((Complex(0,-0.25)/Sqrt(2),1/(4.*Sqrt(2)),0),(1/(4.*Sqrt(2)),Complex(0,0.25)/Sqrt(2),0),(0,0,0))),(((-1/(4.*Sqrt(2)),Complex(0,-0.25)/Sqrt(2),0),(Complex(0,-0.25)/Sqrt(2),1/(4.*Sqrt(2)),0),(0,0,0)),((Complex(0,-0.25)/Sqrt(2),1/(4.*Sqrt(2)),0),(1/(4.*Sqrt(2)),Complex(0,0.25)/Sqrt(2),0),(0,0,0)),((0,0,0),(0,0,0),(0,0,0)))),((((0.25,Complex(0,0.25),0),(Complex(0,0.25),-0.25,0),(0,0,0)),((Complex(0,0.25),-0.25,0),(-0.25,Complex(0,-0.25),0),(0,0,0)),((0,0,0),(0,0,0),(0,0,0))),(((Complex(0,0.25),-0.25,0),(-0.25,Complex(0,-0.25),0),(0,0,0)),((-0.25,Complex(0,-0.25),0),(Complex(0,-0.25),0.25,0),(0,0,0)),((0,0,0),(0,0,0),(0,0,0))),(((0,0,0),(0,0,0),(0,0,0)),((0,0,0),(0,0,0),(0,0,0)),((0,0,0),(0,0,0),(0,0,0))))))
            else: 
                raise ValueError('No Spherical to Cart conversion availble for rank '+str(K))
        else:
            CS=[];
            for i in range(1,K+1):      #generate coupling sequence CS=[1,2,3...K]
                CS+=[i]
            C=np.array(self.StoneCoefficients(CS,k=k)).transpose()   
        return C   
            
    def StoneCoefficients(self, CouplingSequenceList,k=-1j):
        '''
        StoneCoefficients(CouplingSequenceList,k=phase_convention)
        Sympy Spherical-Cartesian conversion coefficients from
        A.J. Stone Molecular Physics 29 1461 (1975) (Equation 1.9)
        CouplingSequenceList is the coupling sequence for spherical tensors, 
            each time coupling to a new vector to form a tensor of given rank
            (sequence always starts with 1)
        k=-I for Condon & Shortley phase convention (default) of k=1 for Racah
        e.g. StoneCoefficients([1,2,3]) returns conversion coefficients for K=3, coupling with 
        maximum rank and Condon & Shortley (default) phase convention
        Example:     C123=StoneCoefficients([1,2,3])    returns conversion matrix for coupling sequence 123 (K=3)
                print(lcontract(C123,3,[1,0,0,0,0,0,0])) returns table values for Q=-3
        Numpy version converted from, Sympy version
        '''
        rt=2**0.5               #sqrt(2)
        #Cartesian index sequence: x,y,z; spherical index sequence -q...+q
        C1=[[1j*k/rt,0,-1j*k/rt],[k/rt,0,k/rt],[0,1j*k,0]]    #coefficients for vector (K=1)=C1
        N=len(CouplingSequenceList)                #total number of vectors coupled    
        #diag('line 311',['rt','C1','N'],locals()) 
        if N==0:
            C=[1]    
        elif N>0:
            C=C1
        if N>1:
            if CouplingSequenceList[0]!=1:
                raise ValueError('First rank in sequence must be 1')
            for J in CouplingSequenceList[1:]:        #loop through all J's after the first
                Cnew=self.StoneCoupleVector(C,J,C1)        #couple to next vector to make tensor of rank J
                C=Cnew     
                #diag('stone coef main loop',['C','J','C1','Cnew'],locals()) 
        return C
       
    def StoneCoupleVector(self, Cold, Knew, C1):
        '''
        StoneCoupleVector(Cold,Knew,C1)
        couple Stone coefficients Cold to a new vector to make coefficient for spherocal tensor of rank Knew
        using vector coupling coefficients C1
        A.J. Stone Molecular Physics 29 1461 (1975) (Equation 1.9)
        Numpy version converted from Sympy version
        '''
        #indexing of Cartesian components=0,1,2 (x,y,z); indexing of spherical components=m+j (0..2j)
        Cold=np.array(Cold); C1=np.array(C1);                  #make sure they are arrays
        oldshape=Cold.shape                            #shape of previous connversion matrix
        newshape=len(oldshape)*[3]+[2*Knew+1]                    #shape of new conversion matrix
        Cnew=np.zeros(newshape, dtype=complex)                            #empty matrix for new conversion matrix
        oldindlist=self.indexlist(oldshape)                       #list of all indices for old matrix
        jn=int((newshape[-1]-1)/2)
        jn_=int((oldshape[-1]-1)/2)                            #j_{n-1} from Stone
        for ind in oldindlist:                            #loop through indices
            ind=list(ind);                  #make sure its a list
            mp=ind[-1]-jn_
            oldelement=Cold[tuple(ind)]                #value of old matrix for index
            for an in range(3):
                for mpp in [-1,0,1]:
                    m=mp+mpp                    #definitions follow Stone...
                    vectorconversion=C1[an][mpp+1]            #required element of vector conversion matrix 
                    cj=self.ClebschGordan(jn_,1,mp,mpp,jn,m)
                    element=Cold[tuple(ind)]        #required element of old conversion matrix
                    newind=ind[:-1]+[an]+[m+jn]            #index for new matrix
                    newelement=Cnew[tuple(newind)]    #element of new matrix
                    newelement+=element*vectorconversion*cj        #add in new bit
                    Cnew[tuple(newind)]=np.copy(newelement)    #save back to array
        return Cnew

    def indexlist(self, shape):
        '''
        indexlist(shape)
        create a list of index lists covering all indices for shape list (all possible indices)
          (Numpy 1.6 has new indexing functionality that my render this obsolete)
        '''
        lenshape=len(shape)                #number of indices
        totalelements=1                    #total number of elements in nested list (start value)
        indlistlist=[]                    #start with empty list of index lists
        indlist=list(range(lenshape))            #single index list placeholder
        multiplicity=list(range(lenshape))        #multiplicities of collumns for counting 
        multiplicity[lenshape-1]=1            #last collumn is 'ones'    
        for i in range(lenshape-2,-1,-1):        
            totalelements*=shape[i+1]
            multiplicity[i]=multiplicity[i+1]*shape[i+1]
        totalelements*=shape[0]
    
        for count in range(totalelements):        #loop through each element (flat index)
            for i in range(lenshape-1,-1,-1):    #loop through indices in reverse order
                indlist[i]=(count//multiplicity[i])%shape[i]    
            indlistlist+=[np.copy(indlist)]
        return indlistlist    

    def ClebschGordan(self, j1, j2, m1, m2, J, M, warn=True):
        """
        ClebschGordan(j1, j2, m1, m2, J, M, cglimit=20,warn=True)
        Computes exact sympy form for Clebsch-Gordan coefficient
        <j1 j2; m1 m2|j1 j2; JM>.
        For reference see
        http://en.wikipedia.org/wiki/Table_of_Clebsch-Gordan_coefficients.
        Clebsch Gordan numpy function by Michael V. DePalatis, modified and converted to sympy by SPC
        warn gives warning for unphysical coefficients
         Adapted from sympy ClebschGordan
        """
        j1=float(j1); j2=float(j2); m1=float(m1); m2=float(m2); J=float(J); M=float(M);
        if not M==(m1+m2) or J>(j1+j2) or J<abs(j1-j2) or J<0 or abs(m1)>j1 or abs(m2)>j2 or abs(M)>J:
            if warn:
                print('Warning: Unphysical Clebsch-Gordan coefficient (j1,j2,m1,m2,J,M)='+str((j1,j2,m1,m2,J,M)))
            return 0
    
        c1 = np.sqrt((2*J+1) * factorial(J+j1-j2) * factorial(J-j1+j2) * \
            factorial(j1+j2-J)/factorial(j1+j2+J+1))
        c2 = np.sqrt(factorial(J+M) * factorial(J-M) * factorial(j1-m1) * \
            factorial(j1+m1) * factorial(j2-m2) * factorial(j2+m2))
        c3 = 0.
        cglimit=max((j1+j2-J),(j1-m1),(j2+m1))+1        #max k that satisfies requirement that all factorial args are non-neg
        for k in np.arange(cglimit):
            use = True
            d = [0, 0, 0, 0, 0]
            d[0] = j1 + j2 - J - k
            d[1] = j1 - m1 - k
            d[2] = j2 + m2 - k
            d[3] = J - j2 + m1 + k
            d[4] = J - j1 -m2 + k
            prod = factorial(k)
            for arg in d:
                if arg < 0:
                    use = False
                    break
                prod *= factorial(arg)
            if use:
                c3 += (-1)**k/prod
        return c1*c2*c3

    
    def spherical_to_cart_tensor(self, Ts):
        K=int((len(Ts)-1)/2); #spherical tensor rank
        C=self.StoneSphericalToCartConversionCoefs(K).conjugate()
        Tc=C[0]*0.0;    #array of zeros
        for kk in range(-K, K+1):
            Tc=Tc+Ts[kk+K]*C[kk+K]
        return Tc
            
    def SF_symmetry(self, R, hkl, spacegroup_list):
        #analyse symmetry of any possible structure factor (mainly for information)
        #returns [sym_phases, gen_scalar_allowed, site_scalar_allowed, tensor_allowed, Psym, Tsym, PTsym]
        tol=1e-6
        identity_mat = np.eye(3)
        inv_mat = -np.eye(3)    

        sym_phases=[];      #list of  symmetry operators (matrices) and the set of phases. Start with empty list.
        Rgen=rand(3);      #use random number to simulate general position to identify spacegroup forbidden reflections
        sum_phase_all=0;    #sum of all phases for site (to get scalar structure factor for site)
        sum_phase_gen=0;    #sum of phases for geneal (random) position
        self.allR = []      #all atomic positions (for diagnostic)
        self.glide_screw = False # change to True if there is a sym op that combines rotation/reflection with translation
        for sym in spacegroup_list:
            mat=sym[0]
            vec=sym[1]
            time=sym[2]
            if not np.allclose(mat, identity_mat, atol=tol) and not np.allclose(mat, inv_mat, atol=tol) \
                and not np.allclose(vec, np.zeros((1,3)), atol=tol):
                self.glide_screw = True
            newR=np.dot(mat, R)+vec
            self.allR += [self.firstCell(newR)] # make list of sites, mapped to first cell (for diagnostic)
            newRgen=np.dot(mat, Rgen)+vec
            phase=np.exp(np.pi*2.j * np.dot(hkl, newR))          
            sum_phase_all+=np.exp(np.pi*2.j * np.dot(hkl, newR))              #add new phase for site to sum
            sum_phase_gen+=np.exp(np.pi*2.j * np.dot(hkl, newRgen))              #add new phase for general (random) position to sum
            newsym=1;
            for sym_phase in sym_phases:
                if np.allclose(mat,sym_phase[0], atol=tol) and np.allclose(time,sym_phase[1], atol=tol):              #compare mat with sym op is sym_phase list
                    newsym=0;                                                       #if already in list then not new
                    sym_phase[2]+=[phase];                                  #add new phase to phse list for sym op
                    break
            if newsym==1:                                                         #sym op not in list so make a new entry
                sym_phases+=[[mat, time, [phase]]]
    
    
        sum_all_phases=0;                       #running total of all phases
        sum_Pplus_Tplus=0   #P even, T even etc
        sum_Pminus_Tplus=0
        sum_Pplus_Tminus=0
        sum_Pminus_Tminus=0
        Psym=Tsym=PTsym=None   #symmetries will be +1, -1 or 0 (even, odd, none)
        gen_scalar_allowed=site_scalar_allowed=1
        tensor_allowed=0
        if abs(sum_phase_all)<tol:
            site_scalar_allowed=0
        if abs(sum_phase_gen)<tol:
            gen_scalar_allowed=0        
        
    
        sum_phases=[]   #sum of phases for each symmetry operator
        for sym_phase in sym_phases:
            sum_phases+=[sum(sym_phase[2])]
            sum_all_phases+=sum(sym_phase[2])                             #add all phases (if all zero then forbidden for scalar)
            if not np.allclose(sum(sym_phase[2]), 0, atol=tol):
                tensor_allowed=1
            if np.allclose(sym_phase[0], identity_mat, atol=tol) and abs(sym_phase[1]-1)<tol:
                sum_Pplus_Tplus+=sum(sym_phase[2])
            elif np.allclose(sym_phase[0], inv_mat, atol=tol) and abs(sym_phase[1]-1)<tol:
                sum_Pminus_Tplus+=sum(sym_phase[2])
            elif np.allclose(sym_phase[0], identity_mat, atol=tol) and abs(sym_phase[1]+1)<tol: #time odd
                sum_Pplus_Tminus+=sum(sym_phase[2])                           
            elif np.allclose(sym_phase[0], inv_mat, atol=tol) and abs(sym_phase[1]+1)<tol:
                sum_Pminus_Tminus+=sum(sym_phase[2])                            
    
    
    #    if tensor_allowed and abs(sum_Pplus_Tplus)>tol: #if there is no item with plus time and plus parity then there is no specific symmetry
        if tensor_allowed: #if there is no item with plus time and plus parity then there is no specific symmetry
            if sum_Pplus_Tplus-sum_Pminus_Tplus==0:
                Psym=+1
            if sum_Pplus_Tplus+sum_Pminus_Tplus==0:
                Psym=-1
            if sum_Pplus_Tplus-sum_Pplus_Tminus==0:
                Tsym=+1
            if sum_Pplus_Tplus+sum_Pplus_Tminus==0:
                Tsym=-1
            if sum_Pplus_Tplus-sum_Pminus_Tminus==0:
                PTsym=+1
            if sum_Pplus_Tplus+sum_Pminus_Tminus==0:
                PTsym=-1
    
        sum_phases=np.array(sum_phases)
        if np.allclose(sum_phases, sum_phases.real, atol=tol):
            sum_phases=np.real(sum_phases)
    
        txtyn=['Yes','Invalid value', 'No', 'Invalid value']; txtoe=['Even', 'Odd', 'Either', 'Either']; 
        #(self.fmt+'[%.1f, %.1f, %.1f]') % ('hkl',self.hkl[0], self.hkl[1], self.hkl[2]) \ ######## remove self - OK??????
        outstr = \
            (self.fmt+'[%.1f, %.1f, %.1f]') % ('hkl',hkl[0], hkl[1], hkl[2]) \
            +(self.fmt+'%s') % ('Site allowed', self.msg(site_scalar_allowed, txt=txtyn)) \
            +(self.fmt+'%.2f+%.2fi') % ('Structure factor for site', np.real(sum_phase_all/len(self.pglist)), np.imag(sum_phase_all/len(self.pglist))) \
            +(self.fmt+'%s') % ('Spacegroup allowed', self.msg(gen_scalar_allowed, txt=txtyn)) \
            +(self.fmt+'%s') % ('Tensor allowed', self.msg(tensor_allowed, txt=txtyn)) \
            +(self.fmt+'%s') % ('Parity', self.msg(Psym, txt=txtoe) ) \
            +(self.fmt+'%s') % ('Time', self.msg(Tsym, txt=txtoe)) \
            +(self.fmt+'%s') % ('PT', self.msg(PTsym, txt=txtoe)) \


    
        sym_sum_phases=deepcopy(sym_phases)
        for ii in range(len(sym_sum_phases)):
            sym_sum_phases[ii][2]=sum_phases[ii]
  
        self.sym_sum_phases, self.sum_phases, self.gen_scalar_allowed, self.site_scalar_allowed, self.tensor_allowed, self.Psym, self.Tsym, self.PTsym, self.sym_phases\
            = sym_sum_phases, sum_phases, gen_scalar_allowed, site_scalar_allowed, tensor_allowed, Psym, Tsym, PTsym, sym_phases

        return outstr
      
    def msg(self, num, txt=['plus','minus','zero','other']):
        #return message text for +1,-1, 0, other (e.g. None)
        if num==1:
            str=txt[0]
        elif num==-1:
            str=txt[1]
        elif num==0:
            str=txt[2]
        else:
            str=txt[3]
        return str
        
        
        
    def spacegroup_list_from_genpos_list(self, genposlist):
        sglist=[];
        for genpos in genposlist:
            sglist+=[self.genpos2matvec(genpos)+[1]] #add +1 to indicate time symmetry
        return sglist    

    def genpos2matvec(self,gen_pos_string):
        'convert general position string to vector/matrix form (floats) using lists as row vectors'
        #gp=gen_pos_string
        gp=gen_pos_string.lower();
        x=y=z=0.; vec=list(eval(gp.replace('/','./')))
        x=1.; y=z=0.; m0=list(eval(gp.replace('/','./'))); m0[0]=m0[0]-vec[0]; m0[1]=m0[1]-vec[1];m0[2]=m0[2]-vec[2];
        y=1.; x=z=0.; m1=list(eval(gp.replace('/','./'))); m1[0]=m1[0]-vec[0]; m1[1]=m1[1]-vec[1];m1[2]=m1[2]-vec[2];
        z=1.; x=y=0.; m2=list(eval(gp.replace('/','./'))); m2[0]=m2[0]-vec[0]; m2[1]=m2[1]-vec[1];m2[2]=m2[2]-vec[2];
        return [np.array([m0, m1, m2]).T, np.array(vec)]       

    def latt2b(self, lat, direct=False, BLstyle=False):
        '''
        follow Busing&Levy, D.E.Sands
        direct=False: normal recip space B matrix (B&L)
        direct=True, BLstyle=True: Busing & Levy style applied to real space (i.e. x||a)
        direct=True, BLstyle=False: Real space B matrix compatible with recip space B matrix
        '''
        a1=lat[0];    a2=lat[1];    a3=lat[2];
        alpha1=lat[3]*np.pi/180;    alpha2=lat[4]*np.pi/180;    alpha3=lat[5]*np.pi/180;
        v=a1*a2*a3*np.sqrt(1-np.cos(alpha1)**2-np.cos(alpha2)**2-np.cos(alpha3)**2+2*np.cos(alpha1)*np.cos(alpha2)*np.cos(alpha3))
        b1=a2*a3*np.sin(alpha1)/v;    b2=a3*a1*np.sin(alpha2)/v;    b3=a1*a2*np.sin(alpha3)/v
        beta1=np.arccos((np.cos(alpha2)*np.cos(alpha3)-np.cos(alpha1))/np.sin(alpha2)/np.sin(alpha3))
        beta2=np.arccos((np.cos(alpha1)*np.cos(alpha3)-np.cos(alpha2))/np.sin(alpha3)/np.sin(alpha1))
        beta3=np.arccos((np.cos(alpha1)*np.cos(alpha2)-np.cos(alpha3))/np.sin(alpha1)/np.sin(alpha2))
        #reciprocal space
        B=np.array([    [b1, b2*np.cos(beta3), b3*np.cos(beta2)],
        [0, b2*np.sin(beta3), -b3*np.sin(beta2)*np.cos(alpha1)],
        [0, 0, 1/a3], ])
        #real space: Busing & Levy style applied to real space (i.e. x||a)
        BD=np.array([    [a1, a2*np.cos(alpha3), a3*np.cos(alpha2)],
        [0, a2*np.sin(alpha3), -a3*np.sin(alpha2)*np.cos(beta1)],
        [0, 0, 1/b3], ])
        # Real space  B matrix consistent with recip space B matrix (useful of calculations involve real and reiprocal space)
        Bdd=inv(B.transpose())
    
        if not direct:
            return B  
        else:
            if BLstyle:
                return BD
            else:
                return Bdd 
            
            
            
    def site_sym(self,spacegroup_list, sitevec):
        symlist=[];
        tol=1e-6;   #coordinates treated as indintical if within tol
        sitevec=(sitevec+tol)%1-tol;      #map into range 0<=x<1 using tolerance tol
        for sg in spacegroup_list:
            newpos=np.dot(sg[0], sitevec)+sg[1]    #new coordinates after applying symmetry operator
            newpos=(newpos+tol)%1-tol;      #map into range 0<=x<1 using tolerance tol
            if np.allclose(newpos, sitevec, atol=.001):    #spacegroup operator presenves position so it is a point group operator
                symlist+=[[sg[0],sg[2]]]                                   #add matrix and time part of sg op to pg but...
                for sym in symlist[0:-1]:
                    if np.allclose(sym[0], sg[0], atol=.001) and abs(sym[1]-sg[2])<tol:     #... remove it again if already in list
                        symlist=symlist[0: -1]
                        break
        return symlist
       
        
    def equiv_sites(self, spacegroup_list, sitevec):
        '''
        equiv_sites(spacegroup_list, sitevec)
        returns symmetry-equivalent sites for selected site
        '''
        poslist=[sitevec];
        tol=1e-6;   #coordinates treated as indintical if within tol
        for sg in spacegroup_list:
            newpos=np.dot(sg[0], sitevec)+sg[1]    #new coordinates after applying symmetry operator
            newpos=(newpos+tol)%1-tol;      #map into range 0<=x<1 using tolerance tol
            poslist+=[newpos]            #add new position to list...
            for pos in poslist[0:-1]:
                if np.allclose(pos, newpos, atol=tol):    #...if position already in list
                    poslist=poslist[0:-1]                                   #...remove it
        return poslist

    def crystal_point_sym(self, spacegroup_list):
        symlist=[]
        tol=1e-6;   #coordinates treated as indintical if within tol
        for sg in spacegroup_list:
            symlist+=[[sg[0],sg[2]]]                         #add matrix  and time part of sg op to pg but...
            for sym in symlist[0:-1]:
                if np.allclose(sym[0], sg[0], atol=tol) and abs(sym[1]-sg[2])<tol:     #... remove it again if already in list
                    symlist=symlist[0: -1]
                    break
        return symlist

    def invert(self):
        '''
        self.invert()
        inverts current spacegroup operators and sites
        '''
        newsg=deepcopy(self.sglist)
        for sgop in newsg:
            sgop[1]=-sgop[1]
        self.sglist = newsg
        self.sitevec = self.firstCell(-self.sitevec)
        return

    def firstCell(self, V):
        #fold V back to first unit cell (0..1)
        return np.array([z-np.floor(z) for z in V])
    
    def isGroup(self, G):
        tol=0.0000001
        #group is a list of [mat, vec, timescalar]
        eye_index=-1
        for ind in range(len(G)):
            if np.all(abs(G[ind][0]-np.eye(3))<tol) and np.all(abs(G[ind][1]-np.zeros(3))<tol) and abs(G[ind][2]-1)<tol:
                eye_index=ind
        if eye_index !=0:
            print('=== Warning: Identity not first element')
        for S1 in G:
            for S2 in G:
                M3=np.dot(S1[0], S2[0])
                V3=self.firstCell(S1[1] + np.dot(S1[0],S2[1]));    #fold back to first unit cell
                T3=S1[2] * S2[2]
                n=0
                for S3 in G:
                    if np.all(abs(M3-S3[0])<tol) and np.all(abs(V3-self.firstCell(S3[1]))<tol) and abs(T3-S3[2])<tol:
                        n+=1
                if n!=1:
                    print('=== Warning: Not a group!')
                    print('=== There should be one occurence of the following symmetry operator but were %i' % n)
                    print(M3, V3, T3, '\n=== Derived from\n', S1, '\n=== and\n', S2)
                    return False
        return True
    

if __name__ == '__main__':
        import TensorScatteringClass as ten

        '''
        print('=== Trying to load crystal data from CIF file...')
        try:
            t1=ten.TensorScatteringClass(CIFfile='ZnO Kisi et al icsd_67454.cif', Site='Zn1')
            t1.PlotIntensityInPolarizationChannels('E1E2', lam=12.4/9.659, hkl=np.array([1,1,1]), hkln=np.array([1,0,0]), K=3, Time=1, Parity=-1, mk=None, sk=None, sigmapi='sigma')
            plt.show()
            t1.print_tensors()
            print('=== Success!')
        except:
            print('=== Failed. Maybe CIF file is missing or CifFile module is not installed')
        '''
        
        print("=== Running test: SG No. 186,  Wyckoff site 'b', E1E2 forbidden reflection (no CIF file needed)")
        try:
            t2=ten.TensorScatteringClass(spacegroup_number = 186, wyckoff_letter = 'b', lattice = [3.25, 3.25, 5.21, 90, 90, 120])
            t2.PlotIntensityInPolarizationChannels('E1E2', lam=12.4/9.659, hkl=np.array([1,1,1]), hkln=np.array([1,0,0]), K=3, Time=1, Parity=-1, mk=None, sk=None, sigmapi='sigma')
            plt.show()
            t2.print_tensors()
            print('=== Success!')
        except:
            print('=== Failed. Maybe CCTBX module is not installed')
        


    
    
class TensorScatteringClassMagrotExtension(TensorScatteringClass):
    
    def PlotIntensityInPolarizationChannelsVsMagrot(self, process, lam, hkl, hkln, psideg=None, K=None, Time=None, Parity=None, mk=None, lk=None, sk=None , sigmapi=None, savefile=None):
        '''
        Extension of TensorScatteringClass with new method to calculate magnetic scattering vs magnet rotation angle
        Moments are rotated about z axis
        psideg must be a scalar
        Plot magrot dependence of sigma or pi intensity and save figure if savefile keyword string (fine name root) given
        '''
        assert sigmapi in ('sigma', 'pi'), "=== sigmapi keyword must be 'sigma' or 'pi'"

        Iss, Isp, Ips, Ipp = [], [], [], []
        magrot = np.array(range(361))
        _mk, _sk, _lk = deepcopy(mk), deepcopy(sk), deepcopy(lk)
        
        
        for rot in magrot:
            m = rot*np.pi/180
            sm, cm = np.sin(m), np.cos(m)
            rotmat = np.array([[cm, -sm, 0],[sm, cm, 0],[0, 0, 1]])
            #rotate any moments specified
            if mk is not None:
                mk = np.dot(rotmat, _mk)
            if sk is not None:
                sk = np.dot(rotmat, _sk)
            if lk is not None:
                lk = np.dot(rotmat, _lk)
            _Iss, _Isp, _Ips, _Ipp = self.CalculateIntensityInPolarizationChannels(process, lam, hkl, hkln, psideg=psideg, K=K, Time=Time, Parity=Parity, mk=mk, lk=lk, sk=sk)
            Iss+=[_Iss]
            Isp+=[_Isp]
            Ips+=[_Ips]
            Ipp+=[_Ipp]
        Iss, Isp, Ips, Ipp = np.array(Iss), np.array(Isp), np.array(Ips), np.array(Ipp)

        
        #sig-sig, sig-pi, sig-total
        titlestr = process+' hkl=[%.1f, %.1f, %.1f]   $\psi_0$=[%.1f, %.1f, %.1f]' % (tuple(hkl)+tuple(hkln)) 

        if sigmapi == 'sigma':
            Ixs, Ixp, Itot, polchar = Iss, Isp, Iss + Isp, '\sigma'
        elif sigmapi == 'pi':
            Ixs, Ixp, Itot, polchar = Ips, Ipp, Ips + Ipp, '\pi'

        plt.figure(); 
        #plt.hold(True);
        plt.plot(magrot, Itot, 'k',label='$\sigma$ Total',linewidth=2.0);
        plt.plot(magrot, Ixs, 'r',label='$'+polchar+'\sigma$',linewidth=2.0);
        plt.plot(magrot, Ixp, 'b',label='$'+polchar+'\pi$',linewidth=2.0); 
        plt.legend(loc='best'); plt.ylabel('Intensity (aribtrary units)'); plt.axis('tight'); plt.xlabel('Magrot (degrees)'); plt.title(titlestr); plt.grid(1)
        if max(abs(Itot)) < 1e-20:
            plt.ylim([0,1])

        plt.show() 
        if savefile != None:
            plt.savefig('%s '+sigmapi+'.pdf' % savefile)




