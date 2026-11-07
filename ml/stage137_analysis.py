"""One frozen geometry experiment with independent risk verification."""
import stage137_prepare
import stage137_fit
import stage137_evaluate
import stage137_validate

if __name__=='__main__':
    stage137_prepare.main()
    stage137_fit.main()
    stage137_evaluate.main()
    stage137_validate.main()

    import stage137_plot
