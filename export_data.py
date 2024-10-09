from io import BytesIO

import pandas as pd
from connect_to_database import  connect_to_database
from datetime import datetime

def export_user_data(user_id):
    conn, cursor = connect_to_database()

    # извлекаем данные
    cursor.execute("""SELECT start_time, p.project_name as project_name, total_work_time
                   FROM time_tracking tt
                   JOIN projects p ON tt.project_id = p.project_id
                   WHERE tt.user_id=?""", (user_id,))
    records = cursor.fetchall()

    if not records:
        return None  # Если данных нет

    #создаем датафрем
    data = []
    for record in records:
        date = datetime.fromtimestamp(record[0]).strftime('%Y-%m-%d')
        project_name = record[1]
        total_minutes = record[2] / 60
        data.append([date, project_name, total_minutes])
    df = pd.DataFrame(data, columns=['date', 'project_name', 'min'])
    df = df.groupby(['date', 'project_name'], as_index=False)['min'].sum()
    df = df.rename(columns={'date':'Дата',
                            'project_name':'Проект',
                            'min':'Количество минут'})

    # создаем файл в памяти
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    conn.close()

    return output #возвращаем файль для отправки

