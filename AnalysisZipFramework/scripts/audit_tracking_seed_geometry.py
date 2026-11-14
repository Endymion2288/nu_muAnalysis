#!/usr/bin/env python3
"""Check angular-prior rotation and seed collinearity from the measured audit."""
import argparse
import gzip
import json
from pathlib import Path

import numpy as np


def direction(phi,theta):
    return np.array([np.cos(phi)*np.sin(theta),np.sin(phi)*np.sin(theta),np.cos(theta)])


def basis(n):
    phi=np.arctan2(n[1],n[0]);theta=np.arctan2(np.hypot(n[0],n[1]),n[2])
    ep=np.array([-np.sin(phi),np.cos(phi),0.]);et=np.array([np.cos(phi)*np.cos(theta),np.sin(phi)*np.cos(theta),-np.sin(theta)])
    return np.column_stack([ep*np.sin(theta),et]),np.vstack([ep/np.sin(theta),et])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with gzip.open(args.audit,'rt') as f:records=[json.loads(l) for l in f]
    seed=next(r for r in records if r['stage']=='seed')
    circle=next(r for r in records if r['stage']=='seed_circle')
    n=direction(*seed['bound'][2:4]);rot=np.array([[0,0,1],[0,1,0],[-1,0,0.]])
    old=rot.T@n;old_derivative,_=basis(old);new_derivative,new_dual=basis(n)
    jac=new_dual@rot@old_derivative
    oldcov=np.diag([.1089,8.41e-6]);newcov=np.array(seed['cov'])[2:4,2:4]
    transformed=jac@oldcov@jac.T
    cov_old_direction=rot@old_derivative@oldcov@old_derivative.T@rot.T
    cov_transformed=new_derivative@transformed@new_derivative.T
    pts=np.array(circle['fake_positions_F']);center=pts[::3]
    slope=(center[-1,1]-center[0,1])/(center[-1,2]-center[0,2])
    chord_at_middle=center[0,1]+slope*(center[1,2]-center[0,2])
    tangent_slopes=[(pts[i+2,1]-pts[i+1,1])/(pts[i+2,2]-pts[i+1,2]) for i in [0,3,6]]
    value=dict(rotation_F_to_A=rot.tolist(),angular_jacobian=jac.tolist(),
        old_angular_covariance_rad2=oldcov.tolist(),production_rotated_angular_covariance_rad2=newcov.tolist(),
        linearly_transformed_old_angular_covariance_rad2=transformed.tolist(),
        linearized_direction_rms_old_mrad=float(np.sqrt(np.trace(cov_old_direction))*1000),
        linearized_direction_rms_production_mrad=float(np.sqrt(np.trace(new_derivative@newcov@new_derivative.T))*1000),
        direction_covariance_closure_max=float(np.abs(cov_old_direction-cov_transformed).max()),
        seed_stations=circle['stations'],seed_momentum_gev=circle['momentum_GeV'],
        seed_reference_radius_mm=circle['momentum_GeV']/(.3*.55*.001),
        segment_center_chord_slope=float(slope),segment_tangent_slopes=tangent_slopes,
        central_y_sagitta_mm=float(center[1,1]-chord_at_middle),
        limitation='Angular Jacobian is a local linearized diagnostic; not a fully calibrated seed covariance, transport, or complete prior equivalence.')
    assert value['direction_covariance_closure_max']<1e-15
    args.output.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value,indent=2))


if __name__=='__main__':main()
