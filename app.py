import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from supabase import create_client, Client

# Cargar variables de entorno desde el archivo .env
load_dotenv()

app = Flask(__name__, template_folder='plantillas', static_folder='static')
app.secret_key = os.getenv("SECRET_KEY", "schestakow_mendoza_secret_2026")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# --- JURISDICCIÓN: INICIO E INSTITUCIONES ---

@app.route('/')
def inicio():
    return redirect(url_for('gestionar_instituciones'))

@app.route('/instituciones', methods=['GET', 'POST'])
def gestionar_instituciones():
    if request.method == 'POST':
        nombre_centro = request.form.get('nombre')
        zona_centro = request.form.get('zona')
        
        try:
            supabase.table('centros_salud').insert({
                "nombre": nombre_centro, 
                "zona": zona_centro
            }).execute()
            flash("Centro de Salud registrado con éxito", "success")
            return redirect(url_for('gestionar_instituciones'))
        except Exception as e:
            flash(f"Error al guardar centro de salud: {str(e)}", "danger")

    try:
        response = supabase.table('centros_salud').select('*').order('id_centros').execute()
        listado_centros = response.data or []
    except Exception as e:
        listado_centros = []
        print(f"Error al conectar con Supabase: {e}")
        
    return render_template('instituciones.html', centros=listado_centros)


# --- JURISDICCIÓN: MAESTRO DE PACIENTES (ABM) ---

@app.route('/pacientes', methods=['GET'])
def gestionar_pacientes():
    id_ver = request.args.get('ver')
    id_editar = request.args.get('editar')
    
    paciente_seleccionado = None
    paciente_editar = None
    historial_turnos = []

    try:
        res_pacientes = supabase.table('pacientes').select('*').order('nombre_apellido').execute()
        lista_pacientes = res_pacientes.data or []
    except Exception as e:
        lista_pacientes = []
        print(f"Error al listar pacientes: {e}")

    if id_ver:
        try:
            res_sel = supabase.table('pacientes').select('*').eq('id_paciente', int(id_ver)).single().execute()
            paciente_seleccionado = res_sel.data
            
            res_turnos = supabase.table('solicitudes_turnos').select(
                'id_solicitud, created_at, especialidad, estado, observaciones, fecha_otorgada, centros_salud(nombre)'
            ).eq('id_paciente', int(id_ver)).order('created_at', desc=True).execute()
            historial_turnos = res_turnos.data or []
        except Exception as e:
            print(f"Error al abrir ficha clínica: {e}")

    if id_editar:
        try:
            res_edit = supabase.table('pacientes').select('*').eq('id_paciente', int(id_editar)).single().execute()
            paciente_editar = res_edit.data
        except Exception as e:
            print(f"Error al cargar edición: {e}")

    return render_template(
        'pacientes.html', 
        lista_pacientes=lista_pacientes, 
        paciente_seleccionado=paciente_seleccionado, 
        paciente_editar=paciente_editar,
        historial_turnos=historial_turnos
    )

@app.route('/pacientes/guardar', methods=['POST'])
def guardar_paciente():
    id_paciente = request.form.get('id_paciente')
    
    datos = {
        "nombre_apellido": request.form.get('nombre_apellido'),
        "dni": request.form.get('dni'),
        "fecha_nacimiento": request.form.get('fecha_nacimiento') or None,
        "telefono": request.form.get('telefono'),
        "nro_hc": request.form.get('nro_hc'),
        "obra_social": request.form.get('obra_social')
    }

    try:
        if id_paciente:
            supabase.table('pacientes').update(datos).eq('id_paciente', int(id_paciente)).execute()
            flash("Datos del paciente actualizados correctamente", "success")
        else:
            supabase.table('pacientes').insert(datos).execute()
            flash("Nuevo paciente registrado con éxito", "success")
            
        return redirect(url_for('gestionar_pacientes'))
    except Exception as e:
        flash(f"Error al guardar paciente: {str(e)}", "danger")
        return redirect(url_for('gestionar_pacientes'))

@app.route('/pacientes/eliminar/', methods=['GET'])
def eliminar_paciente(id):
    try:
        supabase.table('pacientes').delete().eq('id_paciente', int(id)).execute()
        flash("Paciente eliminado correctamente", "success")
    except Exception:
        flash("No se puede eliminar: el paciente posee solicitudes de turnos registradas.", "warning")
    return redirect(url_for('gestionar_pacientes'))


# --- JURISDICCIÓN: AGENTE SANITARIO (SOLICITUD DESDE SALA) ---

@app.route('/solicitud', methods=['GET'])
def cargar_formulario_solicitud():
    try:
        res_centros = supabase.table('centros_salud').select('*').order('nombre').execute()
        centros = res_centros.data or []
        
        res_pacientes = supabase.table('pacientes').select('id_paciente, nombre_apellido, dni, nro_hc').order('nombre_apellido').execute()
        lista_pacientes = res_pacientes.data or []
    except Exception as e:
        centros = []
        lista_pacientes = []
        print(f"Error al inicializar formulario: {e}")

    return render_template('solicitud.html', centros=centros, lista_pacientes=lista_pacientes)

@app.route('/solicitud/guardar', methods=['POST'])
def guardar_solicitud():
    es_nuevo = request.form.get('es_nuevo') == "true"
    
    try:
        if es_nuevo:
            datos_paciente = {
                "nombre_apellido": request.form.get('nombre_apellido'),
                "dni": request.form.get('dni'),
                "fecha_nacimiento": request.form.get('fecha_nacimiento') or None,
                "telefono": request.form.get('telefono'),
                "nro_hc": request.form.get('nro_hc'),
                "obra_social": request.form.get('obra_social')
            }
            res_nuevo_pac = supabase.table('pacientes').insert(datos_paciente).execute()
            id_paciente = res_nuevo_pac.data[0]['id_paciente']
        else:
            id_paciente = int(request.form.get('id_paciente'))

        datos_solicitud = {
            "id_paciente": id_paciente,
            "id_centros": int(request.form.get('id_centros')),
            "especialidad": request.form.get('especialidad'),
            "diagnostico_motivo": request.form.get('diagnostico_motivo'),
            "estado": "pendiente"
        }

        supabase.table('solicitudes_turnos').insert(datos_solicitud).execute()
        flash("Solicitud enviada a Mesa de Entrada del Hospital Schestakow", "success")
        return redirect(url_for('cargar_formulario_solicitud'))

    except Exception as e:
        flash(f"Error al procesar solicitud: {str(e)}", "danger")
        return redirect(url_for('cargar_formulario_solicitud'))


# --- JURISDICCIÓN: MONITOR DE ESTADOS Y MESA DE ENTRADA ---

@app.route('/estado', methods=['GET'])
def ver_estado_solicitudes():
    try:
        res = supabase.table('solicitudes_turnos').select(
            'id_solicitud, created_at, especialidad, diagnostico_motivo, estado, observaciones, fecha_otorgada, '
            'pacientes(nombre_apellido, dni, nro_hc), centros_salud(nombre)'
        ).order('created_at', desc=True).execute()
        
        solicitudes_raw = res.data or []
        for s in solicitudes_raw:
            if s.get('created_at'):
                try:
                    dt = datetime.fromisoformat(s['created_at'].split('.')[0].replace('Z', ''))
                    s['fecha_corta'] = dt.strftime('%d/%m/%Y')
                    s['hora_corta'] = dt.strftime('%H:%M')
                except Exception:
                    s['fecha_corta'], s['hora_corta'] = '--/--/----', '--:--'
            else:
                s['fecha_corta'], s['hora_corta'] = '--/--/----', '--:--'
    except Exception as e:
        solicitudes_raw = []
        print(f"Error en panel de estados: {e}")

    return render_template('estado.html', solicitudes=solicitudes_raw)

@app.route('/gestion', methods=['GET'])
def bandeja_gestion_turnos():
    try:
        res = supabase.table('solicitudes_turnos').select(
            'id_solicitud, created_at, especialidad, diagnostico_motivo, estado, observaciones, fecha_otorgada, '
            'pacientes(nombre_apellido, dni, nro_hc), centros_salud(nombre)'
        ).order('id_solicitud', desc=False).execute()
        
        solicitudes_raw = res.data or []
        for s in solicitudes_raw:
            if s.get('created_at'):
                try:
                    dt = datetime.fromisoformat(s['created_at'].split('.')[0].replace('Z', ''))
                    s['fecha_corta'] = dt.strftime('%d/%m/%Y')
                    s['hora_corta'] = dt.strftime('%H:%M')
                except Exception:
                    s['fecha_corta'], s['hora_corta'] = '--/--/----', '--:--'
            else:
                s['fecha_corta'], s['hora_corta'] = '--/--/----', '--:--'
    except Exception as e:
        solicitudes_raw = []
        print(f"Error en bandeja de recepción: {e}")

    return render_template('gestion.html', solicitudes=solicitudes_raw)

@app.route('/gestion/aceptar', methods=['POST'])
def procesar_aceptacion_turno():
    id_solicitud = request.form.get('id_solicitud')
    fecha_hora_raw = request.form.get('fecha_hora')
    
    try:
        dt = datetime.strptime(fecha_hora_raw, '%Y-%m-%dT%H:%M')
        fecha_formateada = dt.strftime('%d/%m/%Y a las %H:%M hs.')
        
        supabase.table('solicitudes_turnos').update({
            "estado": "asignado",
            "fecha_otorgada": dt.isoformat(),
            "observaciones": f"Turno otorgado para el día: {fecha_formateada}",
            "fecha_modif": datetime.now(timezone.utc).isoformat()
        }).eq('id_solicitud', int(id_solicitud)).execute()
        
        flash("Turno confirmado y notificado a la sala de origen", "success")
        return redirect(url_for('bandeja_gestion_turnos'))
    except Exception as e:
        flash(f"Error al agendar cita: {str(e)}", "danger")
        return redirect(url_for('bandeja_gestion_turnos'))

@app.route('/gestion/rechazar', methods=['POST'])
def procesar_rechazo_turno():
    id_solicitud = request.form.get('id_solicitud')
    motivo = request.form.get('motivo')
    
    try:
        supabase.table('solicitudes_turnos').update({
            "estado": "rechazado",
            "observaciones": f"Rechazado por Mesa de Entrada: {motivo}",
            "fecha_modif": datetime.now(timezone.utc).isoformat()
        }).eq('id_solicitud', int(id_solicitud)).execute()
        
        flash("Solicitud rechazada con justificación cargada", "warning")
        return redirect(url_for('bandeja_gestion_turnos'))
    except Exception as e:
        flash(f"Error al procesar rechazo: {str(e)}", "danger")
        return redirect(url_for('bandeja_gestion_turnos'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)