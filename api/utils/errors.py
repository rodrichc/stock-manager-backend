class AppError(Exception):
    def __init__(self, mensaje, status_code):
        self.mensaje = mensaje
        self.status_code = status_code
        super().__init__(self.mensaje)