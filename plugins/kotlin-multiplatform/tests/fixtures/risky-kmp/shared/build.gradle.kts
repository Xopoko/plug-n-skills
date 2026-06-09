plugins {
    id("org.jetbrains.kotlin.multiplatform")
    id("org.jetbrains.compose")
    id("maven-publish")
    id("co.touchlab.kmmbridge")
}

repositories {
    mavenCentral()
}

kotlin {
    iosArm64()
    iosSimulatorArm64()

    iosArm64().compilations.getByName("main") {
        val nativeCrypto by cinterops.creating {
            packageName("fixture.crypto")
        }
    }

    binaries {
        framework {
            baseName = "RiskyShared"
            export(project(":shared"))
            transitiveExport = true
        }
    }

    swiftPMDependencies {
    }

    sourceSets {
        commonMain.dependencies {
            api("org.example:exported-one:1.0")
        }
        commonTest.dependencies {
        }
    }
}
