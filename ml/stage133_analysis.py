"""Execute the frozen seven fits once, then evaluate and independently verify."""
import stage133_fit
import stage133_evaluate
import stage133_validate

if __name__ == '__main__':
    stage133_fit.main()
    stage133_evaluate.main()
    stage133_validate.main()
    import stage133_plot
