"""Stage66 cal-template / eval local response, reusing frozen stage65 algebra."""
import csv
import numpy as np
from spectrum_hardness import (REPO,REPRESENTATIONS,TERMS,COMPONENTS,grouped_moments,
    source_draws,decompose,local_information,response_vectors,project_response,
    directions,covariance,begin,resources,save)
from response_migration import source_ess

OUT=REPO/'workbook/stage66_energy_ml'
FISHER_FIELDS=['sigma_f_fixed','sigma_f_free','sigma_alpha','parameter_correlation',
              'sigma_f_cost_ratio','normalized_condition','normalized_rank','C_sum','unit_operator_error']
PROJECTION_FIELDS=['fixed_delta_f','free_delta_f','free_delta_alpha','fixed_half_L1',
                   'free_half_L1','fixed_weighted_norm','free_weighted_norm']


def table(path,rows):
    with path.open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def numeric(value):return np.nan if value is None else value


def uncertainty(values):
    use=np.isfinite(values);good=int(use.sum())
    return dict(low95=float(np.quantile(values[use],.025)) if good else None,
        high95=float(np.quantile(values[use],.975)) if good else None,
        valid_replicates=good,invalid_replicates=int((~use).sum()))
