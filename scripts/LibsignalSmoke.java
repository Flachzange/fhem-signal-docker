import org.signal.libsignal.protocol.IdentityKeyPair;

// Generates only an ephemeral local key. No account and no network access.
class LibsignalSmoke {
    public static void main(String[] args) throws Exception {
        var generated = IdentityKeyPair.generate();
        var restored = new IdentityKeyPair(generated.serialize());
        if (!java.util.Arrays.equals(generated.serialize(), restored.serialize())) {
            throw new IllegalStateException("libsignal key round trip failed");
        }
        System.out.println("libsignal JNI key generation and serialization passed");
    }
}
