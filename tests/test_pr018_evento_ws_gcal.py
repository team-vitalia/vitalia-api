from selenium import webdriver
from selenium.webdriver.common.by import By
import time

def test_pr018_evento_ws_gcal():
    driver = webdriver.Chrome()
    driver.get("http://localhost:8081/login")
    time.sleep(2)

    campo_correo = driver.find_element(By.CSS_SELECTOR, '[data-testid="login-email"]')
    driver.execute_script("arguments[0].style.backgroundColor = '#e0f2fe'; arguments[0].style.border = '2px solid #0284c7';", campo_correo)
    time.sleep(2)
    campo_correo.send_keys("jesus.gg@gmail.com")
    time.sleep(2)

    campo_clave = driver.find_element(By.CSS_SELECTOR, '[data-testid="login-password"]')
    driver.execute_script("arguments[0].style.backgroundColor = '#fef9c3'; arguments[0].style.border = '2px solid #ca8a04';", campo_clave)
    time.sleep(2)
    campo_clave.send_keys("password123")
    time.sleep(2)

    boton_login = driver.find_element(By.CSS_SELECTOR, '[data-testid="login-submit"]')
    driver.execute_script("arguments[0].style.backgroundColor = '#fed7aa'; arguments[0].style.border = '2px solid #ea580c';", boton_login)
    time.sleep(2)
    boton_login.click()
    time.sleep(2)

    driver.get("http://localhost:8081/recepcion/citas/crear")
    time.sleep(2)

    selector_paciente = driver.find_element(By.XPATH, "//*[contains(text(), 'Selecciona un paciente')]")
    driver.execute_script("arguments[0].style.backgroundColor = '#e0e7ff'; arguments[0].style.border = '2px solid #4f46e5';", selector_paciente)
    time.sleep(2)
    selector_paciente.click()
    time.sleep(2)

    opcion_paciente = driver.find_element(By.XPATH, "//*[contains(text(), 'Alejandra') or contains(text(), 'Abisag')]")
    driver.execute_script("arguments[0].style.backgroundColor = '#dcfce7'; arguments[0].style.border = '2px solid #16a34a';", opcion_paciente)
    time.sleep(2)
    opcion_paciente.click()
    time.sleep(2)

    selector_doctor = driver.find_element(By.XPATH, "//*[contains(text(), 'Selecciona un doctor')]")
    driver.execute_script("arguments[0].style.backgroundColor = '#fef9c3'; arguments[0].style.border = '2px solid #ca8a04';", selector_doctor)
    time.sleep(2)
    selector_doctor.click()
    time.sleep(2)

    opcion_doctor = driver.find_element(By.XPATH, "//*[contains(text(), 'Cristian')]")
    driver.execute_script("arguments[0].style.backgroundColor = '#dcfce7'; arguments[0].style.border = '2px solid #16a34a';", opcion_doctor)
    time.sleep(2)
    opcion_doctor.click()
    time.sleep(2)

    campo_fecha = driver.find_element(By.XPATH, "//input[@type='date']")
    driver.execute_script("arguments[0].style.backgroundColor = '#fed7aa'; arguments[0].style.border = '2px solid #ea580c';", campo_fecha)
    time.sleep(2)
    driver.execute_script("var s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; s.call(arguments[0], '2026-11-25'); arguments[0].dispatchEvent(new Event('input', { bubbles: true })); arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", campo_fecha)
    time.sleep(2)

    campos_hora = driver.find_elements(By.XPATH, "//input[@type='time']")
    driver.execute_script("arguments[0].style.backgroundColor = '#e0f2fe'; arguments[0].style.border = '2px solid #0284c7';", campos_hora[0])
    time.sleep(2)
    driver.execute_script("var s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; s.call(arguments[0], '10:00'); arguments[0].dispatchEvent(new Event('input', { bubbles: true })); arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", campos_hora[0])
    time.sleep(2)

    driver.execute_script("arguments[0].style.backgroundColor = '#e0f2fe'; arguments[0].style.border = '2px solid #0284c7';", campos_hora[1])
    time.sleep(2)
    driver.execute_script("var s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; s.call(arguments[0], '11:00'); arguments[0].dispatchEvent(new Event('input', { bubbles: true })); arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", campos_hora[1])
    time.sleep(2)

    campo_motivo = driver.find_element(By.XPATH, "//input[@placeholder='Ej. Chequeo preventivo, dolor lumbar...']")
    driver.execute_script("arguments[0].style.backgroundColor = '#fef08a'; arguments[0].style.border = '2px solid #ca8a04';", campo_motivo)
    time.sleep(2)
    campo_motivo.send_keys("Cita Medica VITALIA - Prueba PR-018")
    time.sleep(2)

    driver.execute_script("window.__lastAlert = null; window.alert = function(msg) { window.__lastAlert = msg; };")

    boton_guardar = driver.find_element(By.XPATH, "//*[contains(text(), 'Guardar y Sincronizar Cita')]")
    driver.execute_script("arguments[0].style.backgroundColor = '#dcfce7'; arguments[0].style.border = '2px solid #16a34a';", boton_guardar)
    time.sleep(2)
    boton_guardar.click()
    time.sleep(6)

    alerta_confirmacion = driver.execute_script("return window.__lastAlert;")
    assert alerta_confirmacion is not None
    assert "Cita creada" in alerta_confirmacion or "sincroniz" in alerta_confirmacion

    driver.get("http://localhost:8081/recepcion/citas")
    time.sleep(3)

    cita_creada = driver.find_element(By.XPATH, "//*[contains(text(), 'Cita Medica VITALIA - Prueba PR-018')]")
    driver.execute_script("arguments[0].style.backgroundColor = '#dcfce7'; arguments[0].style.border = '2px solid #16a34a';", cita_creada)
    time.sleep(2)
    assert cita_creada.is_displayed()

    badge_gcal = driver.find_element(By.XPATH, "//*[contains(text(), 'Google Calendar')]")
    driver.execute_script("arguments[0].style.backgroundColor = '#e0f2fe'; arguments[0].style.border = '2px solid #0284c7';", badge_gcal)
    time.sleep(2)
    assert badge_gcal.is_displayed()

    time.sleep(5)
    driver.quit()
