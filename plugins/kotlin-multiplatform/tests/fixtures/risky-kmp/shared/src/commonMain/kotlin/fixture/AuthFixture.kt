package fixture

expect class DeviceSecrets

class AuthFixture {
    val accessToken = "placeholder-token"

    fun refresh() {
        println(accessToken)
        refreshTokens {
        }
    }
}
