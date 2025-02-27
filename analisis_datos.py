def analyze_data(df):
    """
    Analiza los datos y crea las métricas para el dashboard
    """
    if df is None or df.empty:
        return None
    
    # Convertir fecha a datetime para manipulaciones
    df['fecha'] = pd.to_datetime(df['fecha'])
    
    # Analizar por categoría
    category_data = df.groupby('categoria')['importe'].agg(['sum', 'count']).reset_index()
    category_data = category_data.sort_values('sum', ascending=False)
    category_data['percentage'] = (category_data['sum'] / category_data['sum'].sum() * 100).round(1)
    
    # Analizar por empresa (top 10)
    business_data = df.groupby('empresa')['importe'].agg(['sum', 'count']).reset_index()
    business_data = business_data.sort_values('sum', ascending=False).head(10)
    business_data['percentage'] = (business_data['sum'] / business_data['sum'].sum() * 100).round(1)
    
    # Analizar por mes
    df['mes_año'] = df['fecha'].dt.strftime('%Y-%m')
    monthly_data = df.groupby('mes_año')['importe'].sum().reset_index()
    monthly_data = monthly_data.sort_values('mes_año')
    
    # Obtener meses para el gráfico (últimos 12 meses)
    if len(monthly_data) > 12:
        monthly_data = monthly_data.tail(12)
    
    # Analizar por método de pago
    payment_data = df.groupby('forma_pago')['importe'].agg(['sum', 'count']).reset_index()
    payment_data = payment_data.sort_values('sum', ascending=False)
    payment_data['percentage'] = (payment_data['sum'] / payment_data['sum'].sum() * 100).round(1)
    
    # Añadir análisis por día de la semana
    df['dia_semana'] = df['fecha'].dt.strftime('%A')
    weekday_data = df.groupby('dia_semana')['importe'].sum().reset_index()
    
    # Añadir análisis trimestral
    df['trimestre'] = df['fecha'].dt.quarter
    df['año'] = df['fecha'].dt.year
    quarterly_data = df.groupby(['año', 'trimestre'])['importe'].sum().reset_index()
    quarterly_data['periodo'] = quarterly_data['año'].astype(str) + '-Q' + quarterly_data['trimestre'].astype(str)
    quarterly_data = quarterly_data.sort_values(['año', 'trimestre'])
    
    # Obtener las últimas 5 transacciones
    recent_transactions = df.sort_values('fecha', ascending=False).head(5)
    recent_transactions['fecha_str'] = recent_transactions['fecha'].dt.strftime('%Y-%m-%d')
    
    # Calcular KPIs generales
    total_gasto = df['importe'].sum()
    promedio_gasto = df['importe'].mean()
    max_gasto = df['importe'].max()
    num_transacciones = len(df)
    
    # Tendencia respecto al mes anterior
    if len(monthly_data) >= 2:
        ultimo_mes = monthly_data.iloc[-1]['importe']
        penultimo_mes = monthly_data.iloc[-2]['importe']
        tendencia_mensual = ((ultimo_mes - penultimo_mes) / penultimo_mes * 100).round(1) if penultimo_mes > 0 else 0
    else:
        tendencia_mensual = 0
    
    # Gastos por rango
    def get_range(value):
        if value < 10:
            return "Menos de 10€"
        elif value < 50:
            return "10€ - 50€"
        elif value < 100:
            return "50€ - 100€"
        elif value < 500:
            return "100€ - 500€"
        else:
            return "Más de 500€"
    
    df['rango_importe'] = df['importe'].apply(get_range)
    range_data = df.groupby('rango_importe')['importe'].agg(['sum', 'count']).reset_index()
    range_data = range_data.sort_values('rango_importe')
    
    # Preparar los datos para el dashboard
    dashboard_data = {
        'general': {
            'total_gasto': total_gasto,
            'promedio_gasto': promedio_gasto,
            'max_gasto': max_gasto,
            'num_transacciones': num_transacciones,
            'tendencia_mensual': tendencia_mensual
        },
        'categorias': category_data.to_dict('records'),
        'empresas': business_data.to_dict('records'),
        'meses': {
            'labels': monthly_data['mes_año'].tolist(),
            'values': monthly_data['importe'].tolist()
        },
        'metodos_pago': payment_data.to_dict('records'),
        'transacciones_recientes': [],
        'por_dia_semana': weekday_data.to_dict('records'),
        'trimestral': {
            'labels': quarterly_data['periodo'].tolist(),
            'values': quarterly_data['importe'].tolist()
        },
        'rangos': range_data.to_dict('records')
    }
    
    # Formatear transacciones recientes para el dashboard
    for _, row in recent_transactions.iterrows():
        dashboard_data['transacciones_recientes'].append({
            'fecha': row['fecha_str'],
            'empresa': row['empresa'],
            'descripcion': row['descripcion'],
            'importe': row['importe'],
            'categoria': row['categoria']
        })
    
    return dashboard_data