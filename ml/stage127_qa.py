"""Small exact checks of weighted errors, rectangle boundaries and parent queries."""
import json
import numpy as np
from stage127_scan import (ROOT,OUT,CACHE,arrays,load,candidates,basic,rectangle,parent_count,Bootstrap)
from stage127_coordinates import histogram_edges
from stage126_report import metrics


def main():
    p=json.loads((OUT/'protocol.json').read_text());d,coords=load();cohort=d['evaluation_role']=='cal'
    small={k:d[k][cohort] for k in ['incoming','direct_cal','truth_E_GeV','x','y']}
    _,small['key']=np.unique(small['incoming'],axis=0,return_inverse=True)
    small['e']=small['direct_cal']-np.log(small['truth_E_GeV']);small['frac']=np.expm1(small['e'])
    grid=candidates(p);checks=[]
    for i in [0,1234,12000,len(grid)-1]:
        c=grid[i];mask=rectangle(d,c);a=basic(small,rectangle(small,c));b=metrics(d,cohort&mask)
        assert a['N']==b['N'] and a['unique_incoming']==b['unique_incoming']
        np.testing.assert_allclose(a['log_RMSE'],b['log_RMSE'],rtol=1e-13)
        np.testing.assert_allclose(a['tail50'],b['tail50'],rtol=1e-13)
        checks.append(dict(candidate_id=i,N=a['N'],log_RMSE=a['log_RMSE']))
    c={'cx':0,'cy':0,'hx':40,'hy':40}
    xx=np.array([-40.,np.nextafter(-40.,np.inf),0.,40.,0.,39.,-39.])
    yy=np.array([0.,0.,0.,0.,40.,-40.,39.])
    ex,ey=histogram_edges(p)
    hist=np.histogram2d(xx,yy,bins=[ex,ey])[0].astype(int)
    synthetic=dict(edges_x=ex,edges_y=ey,hist50=hist,hist100=hist)
    assert parent_count(synthetic,c,'pz50')==3
    mask=rectangle(dict(x=xx,y=yy),c);assert mask.tolist()==[False,True,True,False,False,False,True]
    boot=Bootstrap(d,cohort,20261106127)
    result=boot.compare(d['radius_mm']<100,d['radius_mm']<100)
    assert result['log_RMSE_ratio_low95']==result['log_RMSE_ratio_high95']==1
    assert len(grid)==25375 and coords['hist50'].sum()==618779
    (OUT/'QA.json').write_text(json.dumps(dict(passed=True,grid_candidates=len(grid),weighted_arithmetic=checks,
       strict_boundary_parent_count_exact=True,paired_identity_interval_exact=True,new_fits=0,new_model_forwards=0),indent=2)+'\n')
    print('Small exact QA passed')


if __name__=='__main__':main()
