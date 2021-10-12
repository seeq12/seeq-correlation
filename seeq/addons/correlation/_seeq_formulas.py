import textwrap
from seeq import sdk
from seeq.sdk.rest import ApiException

pearson_formula = textwrap.dedent(
    """
    $condition = periods($window, $period)
    $s1 = $signal1.setUnits('')
    $s2 = $signal2.setUnits('')
    // intermediate calculations
    $s1_sq = $s1^2
    $s2_sq = $s2^2
    $s1s2_product = ($s1 * $s2)
    $N = $s1.aggregate(count(), $condition, middleKey(), 0h)
    // Pearson's coefficient
    $numerator = $N * $s1s2_product.aggregate(sum(), $condition, middleKey(), 0h) - $s1.aggregate(sum(), $condition, 
    middleKey(), 0h) * $s2.aggregate(sum(), $condition, middleKey(), 0h)
    $denominator = sqrt(($N * $s1_sq.aggregate(sum(), $condition, middleKey(), 0h) - ($s1.aggregate(sum(), $condition, 
    middleKey(), 0h))^2) * ($N * $s2_sq.aggregate(sum(), $condition, middleKey(), 0h) - ($s2.aggregate(sum(), 
    $condition, middleKey(), 0h))^2))
    ($numerator / $denominator).aggregate(average(), $condition, middleKey())
    """)

pearson_timeshifted_formula = textwrap.dedent(
    """
    $s1_o = $signal.setUnits('')
    $s2 = $goal.setUnits('')
    
    $Wind = periods($window, $period)
    $Wind.tosamples( $cap -> {
        // get the time shift to maximize cross-correlation
        $time_shift = $signal.correlationOffset($goal, group($cap), -$maxOffset , $maxOffset, $correlation_threshold)
        // shift the signal
        $s1 = $s1_o.move($time_shift)
        $s1_sq = $s1^2
        $s2_sq = $s2^2
        $s1s2_product = ($s1 * $s2)
        $N = $s1.count($cap)
        // Pearson's coefficient
        $numerator = $N * $s1s2_product.sum($cap) - $s1.sum($cap) * $s2.sum($cap)
        $denominator = sqrt(($N * $s1_sq.sum($cap) - ($s1.sum($cap))^2) * ($N * $s2_sq.sum($cap) - ($s2.sum($cap))^2))
        $pearson = ($numerator / $denominator)
        sample($cap.middleKey(),$pearson)},$window)
    """)

time_shifts_formula = textwrap.dedent(
    """
    $Wind = periods($window, $period)
    $Wind.tosamples( $cap -> {
        $value = $signal.correlationOffset($goal,group($cap), -$maxOffset, $maxOffset, $correlation_threshold)
        sample($cap.middleKey(),$value)},$window)
    """)

# Create the User Defined Formula Functions
signal_input = sdk.FormulaParameterInputV1(name='signal', formula='1.toSignal()', unbound=True)
signal_input1 = sdk.FormulaParameterInputV1(name='signal1', formula='1.toSignal()', unbound=True)
signal_input2 = sdk.FormulaParameterInputV1(name='signal2', formula='1.toSignal()', unbound=True)
goal_input = sdk.FormulaParameterInputV1(name='goal', formula='1.toSignal()', unbound=True)
window_input = sdk.FormulaParameterInputV1(name='window', formula='1h', unbound=True)
period_input = sdk.FormulaParameterInputV1(name='period', formula='1h', unbound=True)
corr_thrs_input = sdk.FormulaParameterInputV1(name='correlation_threshold', formula='1', unbound=True)
maxtimeshift_input = sdk.FormulaParameterInputV1(name='maxOffset', formula='1h', unbound=True)

formulas_info = [
    dict(function_name='correlationCoefficient',
         formula=pearson_formula,
         args=[signal_input1, signal_input2, window_input, period_input],
         description=textwrap.dedent(
             """
             <p>Calculates the rolling window Pearson's correlation coefficients between two signals. 
            One correlation coefficient is calculated for the data contained within each <code>window</code> of time. 
            The <code>period</code> dictates the step the <code>window</code> is moved (or rolled) for the next 
            coefficient calculation.</p>
            """),
         examples=[
             sdk.FormulaDocExampleInputV1(
                 description="Calculate the Pearson's correlation coefficients between <code>$signal1</code> and "
                             "<code>$signal2</code> during a 24 hour interval and move the window every 6 hours",
                 formula='CrossCorrelations_correlationCoefficient($signal1, $signal2, 24h, 6h)')
         ]
         ),
    dict(function_name='correlationCoefficientWithTimeShifts',
         formula=pearson_timeshifted_formula,
         args=[signal_input, goal_input, window_input, period_input, corr_thrs_input, maxtimeshift_input],
         description=textwrap.dedent(
             """
             <p>Calculates the rolling window maximum Pearson's correlation coefficients between two sliding signals. 
             For each <code>window</code>, the time shift that maximizes the cross-correlation between the two 
             signals is determined first. Then, the samples inside the window are time shifted 
             (the <code>goal</code> signal is kept fixed and the other <code>window</code> is shifted). Finally, 
             the maximum correlation coefficient coefficient for the <code>window</code> is calculated and its value 
             becomes one sample of the output signal. The process repeats after rolling the window a given 
             <code>period</code>.</p>  
             <p>This formula uses the <sq-link href="/formulas/docs/Seeq/correlationOffset"> 
             <a href="" ng-click="$ctrl.sqPowerSearch.requestDocumentation($ctrl.href)" 
             ng-transclude="">correlationOffset() </a></sq-link> formula to calculate the time shifts for each window. 
             See <sq-link href="/formulas/docs/Seeq/correlationOffset"> 
             <a href="" ng-click="$ctrl.sqPowerSearch.requestDocumentation($ctrl.href)" 
             ng-transclude="">correlationOffset() </a></sq-link>  
             for more information on the <code>maxOffset</code> and <code>correlation_threshold</code> parameters</p>  
             <p><i>Note: The <strong>correlationCoefficientWithTimeShifts</strong> assumes the <code>minOffset</code> in  
             <sq-link href="/formulas/docs/Seeq/correlationOffset"> 
             <a href="" ng-click="$ctrl.sqPowerSearch.requestDocumentation($ctrl.href)" 
             ng-transclude="">correlationOffset() </a></sq-link> to be equal to <code>-maxOffset</code>.</i></p>
         """),
         examples=[
             sdk.FormulaDocExampleInputV1(
                 description="Calculate the maximum Pearson's correlation coefficients between <code>$signal</code> "
                             "and <code>$goal</code> in 24 h intervals that step every 6 hours, if <code>$signal</code>"
                             " is allowed to shift in time with respect to <code>$goal</code>",
                 formula='CrossCorrelations_correlationCoefficientWithTimeShifts($signal, $goal, 24h, 6h, 0.8, 2h)')
         ],
         ),
    dict(function_name='timeShifts',
         formula=time_shifts_formula,
         args=[signal_input, goal_input, window_input, period_input, corr_thrs_input, maxtimeshift_input],
         description=textwrap.dedent(
             """
             <p>Calculates the rolling window  
             <sq-link href="/formulas/docs/Seeq/correlationOffset"> 
             <a href="" ng-click="$ctrl.sqPowerSearch.requestDocumentation($ctrl.href)" 
             ng-transclude="">correlationOffset() </a></sq-link> between <code>signal</code> and <code>goal</code> 
             That is, the time shift that maximizes the cross-correlation between the two signals is determined for 
             each <code>window</code> using the <sq-link href="/formulas/docs/Seeq/correlationOffset"> 
             <a href="" ng-click="$ctrl.sqPowerSearch.requestDocumentation($ctrl.href)" 
             ng-transclude="">correlationOffset() 
             </a></sq-link> formula. The process repeats after rolling the window a given <code>period</code>.</p> 
            """
         ),
         examples=[
             sdk.FormulaDocExampleInputV1(
                 description=textwrap.dedent(
                     """
                     Calculate the dynamic time shifts to maximize cross-correlation between <code>$signal</code> 
                     and <code>$goal</code> in 24 h intervals  every 6 hours, if <code>$signal</code> is allowed 
                     to shift in time with respect to <code>$goal</code>
                     """
                 ),
                 formula='CrossCorrelations_timeShifts($signal, $goal, 24h, 6h, 0.8, 2h)')
         ],
         )
]


def correlation_udfs(api_client):
    """
    This function creates Cross Correlation package of User Defined Functions
    in the Seeq server. Once installed, these formula functions can be used
    either standalone in the Seeq server, or called by the Correlation
    Analysis Add-On for more interactive calculations

    Parameters
    ----------
    api_client: spy.client, default None
        Authenticated Seeq client

    Returns
    -------
    package.id: str
        The ID of the Seeq UDF package
    """
    package_name = 'CrossCorrelations'
    creator_name = 'Alberto Rivas'
    creator_contact_info = 'applied.research@seeq.com'
    formulas_api = sdk.FormulasApi(api_client)
    try:
        pkg = formulas_api.get_package(package_name=package_name)
        if pkg.name == package_name:
            print(f"Overwriting CrossCorrelation package")
            formulas_api.delete_package(package_name=package_name)
    except ApiException as e:
        if 'not found' in e.reason.lower():
            pass
        else:
            raise e

    # Create the Formula Package
    package_input = sdk.FormulaPackageInputV1(creator_name=creator_name, creator_contact_info=creator_contact_info)
    package_output = formulas_api.put_package(package_name=package_name, body=package_input)

    # Create the individual formulas
    for formula in formulas_info:
        print(f"Creating formula {formula['function_name']}")
        create_udf_formulas(formulas_api, package_name, formula['function_name'], formula['formula'], *formula['args'])

    # Create the formula docs
    formula_pkg_docs(package_name, formulas_api)

    return package_output.id


def create_udf_formulas(formulas_api, pkg_name, function_name, formula, *args):
    udf_input = sdk.FunctionInputV1(package_name=pkg_name,
                                    name=function_name,
                                    type='UserDefinedFormulaFunction',
                                    formula=formula,
                                    parameters=list(args))
    formulas_api.create_function(body=udf_input)


def formula_pkg_docs(package_name, formulas_api: sdk.FormulasApi):
    # Create formula docs
    index_title = 'Cross Correlation'
    index_description = textwrap.dedent(
        """
        Computes the cross-correlations between two signals and allows signals to time shift to maximize the 
        cross-correlation
        """)
    index_doc_input = sdk.FormulaDocInputV1(
        title=index_title,
        description=index_description,
        search_keywords=sdk.FormulaDocKeywordListInputV1(keywords=[
            'cross-correlation', 'correlation', 'Pearson', 'offset', 'time shifts']))
    formulas_api.put_formula_doc(
        package_name=package_name,
        doc_name='index',
        body=index_doc_input)

    # Create the docs for each formula
    for formula in formulas_info:
        formula_docs(package_name, formula['function_name'], formula['description'],
                     sdk.FormulaDocExampleListInputV1(examples=formula['examples']), formulas_api)


def formula_docs(pkg_name, function_name, description, examples: sdk.FormulaDocExampleListInputV1,
                 formulas_api: sdk.FormulasApi):
    # Examples are the best way to demonstrate using the UDF.
    doc_input = sdk.FormulaDocInputV1(description=description,
                                      examples=examples)
    formulas_api.put_formula_doc(package_name=pkg_name,
                                 doc_name=function_name,
                                 body=doc_input)


def signals_from_formula(signal1_id, signal_ref_id, workbook_id, formula_type=None, output_signal_name=None,
                         suffix='', api_client: sdk.api_client = None, **kwargs):
    signals_api = sdk.SignalsApi(api_client)
    if formula_type is None:
        raise ValueError("formula_type can't be None")
    if formula_type == 'pearson':
        formula = textwrap.dedent(
            f"""
            $window = {kwargs['window']}
            $period = {kwargs['period']}
            CrossCorrelations_correlationCoefficient($signal, $goal, $window, $period)
        """
        )
        signal_name_prefix = f"Correlation Coefficient:"
        signal_name_middle = "||"

    elif formula_type == 'time_shifts':
        formula = textwrap.dedent(
            f"""
            $window = {kwargs['window']}
            $period = {kwargs['period']}
            $correlation_threshold = {kwargs['corr_threshold']}
            $max_time_shift = {kwargs['max_time_shift']}
            $time_unit = '{kwargs['output_time_unit']}'
            CrossCorrelations_timeShifts($signal, $goal, $window, $period, $correlation_threshold, 
            $max_time_shift).convertUnits($time_unit)
        """
        )
        signal_name_prefix = f"Time Shifts: "
        signal_name_middle = "||aligned_to||"
    elif formula_type == 'pearson_with_time_shifts':
        formula = textwrap.dedent(
            f"""
            $window = {kwargs['window']}
            $period = {kwargs['period']}
            $correlation_threshold = {kwargs['corr_threshold']}
            $max_time_shift = {kwargs['max_time_shift']}
            CrossCorrelations_correlationCoefficientWithTimeShifts($signal, $goal, $window, $period, $correlation_threshold, 
            $max_time_shift)
        """
        )
        signal_name_prefix = f"Correlation with Dynamic Time Shifting: "
        signal_name_middle = "||"
    else:
        raise ValueError(f"formula name '{formula_type}' is not a valid option")

    if output_signal_name is None:
        signal1_name = signals_api.get_signal(id=signal1_id).name
        signal2_name = signals_api.get_signal(id=signal_ref_id).name
        output_signal_name = f"{signal_name_prefix} {signal1_name} {signal_name_middle} {signal2_name} {suffix}"
    payload = dict(name=f"{output_signal_name}",
                   formula=formula,
                   formulaParameters=[f"signal={signal1_id}",
                                      f"goal={signal_ref_id}"],
                   scopedTo=workbook_id
                   )
    r = signals_api.create_signal_with_http_info(body=payload)[0]
    return r
