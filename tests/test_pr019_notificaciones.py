from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import requests

def test_pr019_notificaciones():
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

    driver.get("http://localhost:8081/notificaciones")
    time.sleep(3)

    estado_ws = driver.find_element(By.XPATH, "//*[text()='CONNECTED']")
    driver.execute_script("arguments[0].style.backgroundColor = '#dcfce7'; arguments[0].style.border = '2px solid #16a34a';", estado_ws)
    time.sleep(2)
    assert estado_ws.is_displayed()

    campana_menu = driver.find_element(By.XPATH, "//*[contains(text(), 'Notificaciones')]")
    driver.execute_script("arguments[0].style.backgroundColor = '#fed7aa'; arguments[0].style.border = '2px solid #ea580c';", campana_menu)
    time.sleep(2)

    requests.post(
        "http://127.0.0.1:8000/ws/broadcast-test",
        json={
            "type": "broadcast_notification",
            "title": "Aviso General VITALIA",
            "body": "Notificación masiva enviada a todos los usuarios conectados en tiempo real."
        }
    )

    toast_elemento = None
    for _ in range(25):
        toasts = driver.find_elements(By.CSS_SELECTOR, "[data-gooey-toast]")
        if toasts and toasts[0].is_displayed():
            toast_elemento = toasts[0]
            break
        time.sleep(0.2)

    assert toast_elemento is not None
    driver.execute_script("arguments[0].dispatchEvent(new MouseEvent('mouseenter', { bubbles: true })); arguments[0].style.backgroundColor = '#dcfce7'; arguments[0].style.border = '3px solid #16a34a';", toast_elemento)
    time.sleep(2)
    assert toast_elemento.is_displayed()

    titulo_toast = driver.find_element(By.CSS_SELECTOR, "[data-gooey-title]")
    driver.execute_script("arguments[0].style.backgroundColor = '#fef08a'; arguments[0].style.border = '2px solid #ca8a04';", titulo_toast)
    time.sleep(2)
    assert "Aviso General VITALIA" in titulo_toast.text

    desc_toast = driver.find_element(By.CSS_SELECTOR, "[data-gooey-description]")
    driver.execute_script("arguments[0].style.backgroundColor = '#e0f2fe'; arguments[0].style.border = '2px solid #0284c7';", desc_toast)
    time.sleep(2)
    assert "Notificación masiva enviada a todos los usuarios conectados en tiempo real." in desc_toast.text

    driver.execute_script("arguments[0].style.backgroundColor = '#e9d5ff'; arguments[0].style.border = '2px solid #9333ea';", campana_menu)
    time.sleep(2)

    time.sleep(5)
    driver.quit()
