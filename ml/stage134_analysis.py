"""Execute the frozen three fits once, then evaluate and independently verify."""
import stage134_fit
import stage134_evaluate
import stage134_validate

if __name__ == '__main__':
    stage134_fit.main()
    stage134_evaluate.main()
    stage134_validate.main()
    import stage134_plot
