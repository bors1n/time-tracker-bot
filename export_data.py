from io import BytesIO

import pandas as pd
from connect_to_database import database_connection
from datetime import datetime

def export_user_data(user_id):
    with database_connection() as (conn, cursor):
        # Extract data
        cursor.execute("""SELECT start_time, p.project_name as project_name, total_work_time
                       FROM time_tracking tt
                       JOIN projects p ON tt.project_id = p.project_id
                       WHERE tt.user_id=?""", (user_id,))
        records = cursor.fetchall()

    if not records:
        return None  # If there's no data

    # Create dataframe
    data = []
    for record in records:
        date = datetime.fromtimestamp(record[0]).strftime('%Y-%m-%d')
        project_name = record[1]
        total_minutes = record[2] / 60
        data.append([date, project_name, total_minutes])
    df = pd.DataFrame(data, columns=['date', 'project_name', 'min'])
    df['min'] = df['min'].round(1)
    df = df.groupby(['date', 'project_name'], as_index=False)['min'].sum()
    df = df.rename(columns={'date':'Дата',
                            'project_name':'Проект',
                            'min':'Количество минут'})

    # Create file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)

    return output  # Return file for sending
