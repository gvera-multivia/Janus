class Cliente:

    def __init__(self, nif, nombre, email, id_redtrust):
        self.nif = nif
        self.nombre = nombre
        self.email = email
        self.id_redtrust = id_redtrust

    def __repr__(self):
        return f"Cliente({self.nif}, {self.nombre})"
