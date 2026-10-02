"""Human-facing formatting; never round a numerical model or saved config."""
def display_number(value):
    if value is None:return '待提供 / 未评估'
    if value!=0 and (abs(value)<.01 or abs(value)>=1e6):
        mantissa,exponent=f'{value:.2e}'.split('e')
        return f'{float(mantissa):g}e{int(exponent)}'
    return f'{value:.2f}'.rstrip('0').rstrip('.')
