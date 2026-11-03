from selenium import webdriver
from selenium.webdriver.common.by import By
import time

def test_pr016_conexion_websockets():
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
    time.sleep(2)

    etiqueta_canal = driver.find_element(By.XPATH, "//*[contains(text(), 'Canal en tiempo real')]")
    driver.execute_script("arguments[0].style.backgroundColor = '#e9d5ff'; arguments[0].style.border = '2px solid #9333ea';", etiqueta_canal)
    time.sleep(2)

    estado_ws = driver.find_element(By.XPATH, "//*[text()='CONNECTED']")
    driver.execute_script("arguments[0].style.backgroundColor = '#dcfce7'; arguments[0].style.border = '2px solid #16a34a';", estado_ws)
    time.sleep(2)

    assert estado_ws.is_displayed()
    assert "CONNECTED" in estado_ws.text

    time.sleep(5)
    driver.quit()
